"""注册完成后自动推送账号到 Any2API 实例。

在全局配置中设置 Any2API 的地址和管理密码后，
每次注册成功都会自动将账号推送到 Any2API，无需手动导出导入。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class Any2ApiClient:
    """Any2API 管理 API 客户端。"""

    def __init__(self, base_url: str, password: str, *, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self._session_cookie = ""

    def _login(self) -> bool:
        try:
            resp = requests.post(
                f"{self.base_url}/admin/api/login",
                json={"password": self.password},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    # Extract session cookie
                    self._session_cookie = resp.cookies.get(
                        "newplatform2api_admin_session", ""
                    ) or data.get("token", "")
                    return True
            logger.warning(f"[Any2API] 登录失败: HTTP {resp.status_code}")
            return False
        except Exception as exc:
            logger.warning(f"[Any2API] 登录异常: {exc}")
            return False

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _cookies(self) -> dict:
        if self._session_cookie:
            return {"newplatform2api_admin_session": self._session_cookie}
        return {}

    def _ensure_login(self) -> bool:
        if self._session_cookie:
            return True
        return self._login()

    def _post(self, path: str, body: dict) -> Optional[dict]:
        if not self._ensure_login():
            return None
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                json=body,
                headers=self._headers(),
                cookies=self._cookies(),
                timeout=self.timeout,
            )
            if resp.status_code == 401:
                # Session expired, retry login
                self._session_cookie = ""
                if not self._login():
                    return None
                resp = requests.post(
                    f"{self.base_url}{path}",
                    json=body,
                    headers=self._headers(),
                    cookies=self._cookies(),
                    timeout=self.timeout,
                )
            return resp.json() if resp.status_code == 200 else None
        except Exception as exc:
            logger.warning(f"[Any2API] POST {path} 失败: {exc}")
            return None

    def _put(self, path: str, body: dict) -> Optional[dict]:
        if not self._ensure_login():
            return None
        try:
            resp = requests.put(
                f"{self.base_url}{path}",
                json=body,
                headers=self._headers(),
                cookies=self._cookies(),
                timeout=self.timeout,
            )
            if resp.status_code == 401:
                self._session_cookie = ""
                if not self._login():
                    return None
                resp = requests.put(
                    f"{self.base_url}{path}",
                    json=body,
                    headers=self._headers(),
                    cookies=self._cookies(),
                    timeout=self.timeout,
                )
            return resp.json() if resp.status_code == 200 else None
        except Exception as exc:
            logger.warning(f"[Any2API] PUT {path} 失败: {exc}")
            return None

    def push_chatgpt(self, access_token: str) -> bool:
        result = self._put("/admin/api/providers/chatgpt/config", {
            "config": {"token": access_token},
        })
        return result is not None

    def push_windsurf(self, api_key: str, *, name: str = "", proxy_url: str = "") -> bool:
        result = self._post("/admin/api/providers/windsurf/accounts/create", {
            "id": str(uuid.uuid4()),
            "name": name or "Auto Register",
            "apiKey": api_key,
            "proxyUrl": proxy_url,
            "active": True,
        })
        return result is not None


def _get_any2api_config() -> tuple[str, str]:
    """从全局配置读取 Any2API 地址和密码。"""
    try:
        from core.config_store import config_store
        base_url = config_store.get("any2api_url", "")
        password = config_store.get("any2api_password", "")
        return base_url, password
    except Exception:
        return "", ""


def push_account_to_any2api(account: Any, *, log_fn=None) -> bool:
    """注册完成后自动推送账号到 Any2API。

    Args:
        account: BasePlatform.Account 对象
        log_fn: 日志函数

    Returns:
        True if pushed successfully, False otherwise (including when not configured)
    """
    log = log_fn or logger.info
    base_url, password = _get_any2api_config()
    if not base_url:
        return False  # Not configured, silently skip

    platform = getattr(account, "platform", "")
    email = getattr(account, "email", "")
    extra = dict(getattr(account, "extra", {}) or {})

    client = Any2ApiClient(base_url, password)

    try:
        if platform == "chatgpt2":
            token = extra.get("access_token", "") or getattr(account, "token", "")
            if token:
                ok = client.push_chatgpt(token)
                if ok:
                    log(f"  [Any2API] ✓ ChatGPT2 账号已推送")
                return ok

        else:
            log(f"  [Any2API] 平台 {platform} 暂不支持自动推送")
            return False

    except Exception as exc:
        log(f"  [Any2API] 推送失败: {exc}")
        return False

    return False
