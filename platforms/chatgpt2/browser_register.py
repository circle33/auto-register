"""ChatGPT2 浏览器注册 worker —— Camoufox 自动化注册登录流程。

流程:
  1. chatgpt.com → 点击登录按钮
  2. 等待登录表单 → 输入邮箱 → 提交
  3. auth.openai.com/email-verification → 输入 OTP（从邮箱获取）→ 提交
  4. auth.openai.com/about-you → 填写姓名年龄 → 提交
  5. 回跳 chatgpt.com → OAuth 授权码流程 → 获取 refresh_token
  6. 收集 cookies / session_token / access_token / refresh_token
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Callable, Optional
from urllib.parse import urlparse, parse_qs

from camoufox.sync_api import Camoufox
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

# OAuth 常量 — 使用 Codex CLI 客户端（Hydra OAuth，支持 refresh_token）
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"       # Codex CLI client
OAUTH_REDIRECT_URI = "http://localhost:1455/auth/callback" # Codex 回调
OAUTH_AUTH_URL = "https://auth.openai.com/oauth/authorize" # Hydra OAuth 端点
OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
OAUTH_SCOPE = "openid email profile offline_access"


def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sha256_b64url(s: str) -> str:
    return _b64url(hashlib.sha256(s.encode()).digest())


def _generate_oauth_params() -> dict:
    """生成 OAuth PKCE 参数，返回 {auth_url, state, code_verifier}。"""
    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _sha256_b64url(code_verifier)

    params = {
        "client_id": OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    import urllib.parse
    auth_url = f"{OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return {"auth_url": auth_url, "state": state, "code_verifier": code_verifier}


def _exchange_code_for_tokens(code: str, code_verifier: str, proxy: str = None) -> dict:
    """用授权码交换 access_token + refresh_token + id_token。"""
    import urllib.request
    import ssl

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": OAUTH_CLIENT_ID,
        "code": code,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "code_verifier": code_verifier,
    }).encode()

    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )

    ctx = ssl.create_default_context()
    if proxy:
        import urllib.request as _ur
        # 通过代理请求需要特殊处理，这里用 curl_cffi
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": OAUTH_CLIENT_ID,
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
            proxy=proxy,
            impersonate="chrome120",
            timeout=30,
        )
        result = resp.json()
    else:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read())

    return {
        "access_token": result.get("access_token", ""),
        "refresh_token": result.get("refresh_token", ""),
        "id_token": result.get("id_token", ""),
        "expires_in": result.get("expires_in", 3600),
    }


def _extract_code_from_url(url: str) -> str | None:
    """从 OAuth 回调 URL 提取授权码。"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get("code", [None])[0]


from .constants import (
    ABOUT_YOU_SUBMIT_XPATH,
    ABOUT_YOU_URL,
    AGE_INPUT_XPATH,
    CHATGPT_APP,
    EMAIL_FORM_XPATH,
    EMAIL_INPUT_FALLBACK,
    EMAIL_INPUT_XPATH,
    EMAIL_SUBMIT_XPATH,
    EMAIL_VERIFICATION_URL,
    ELEMENT_WAIT_TIMEOUT,
    LOGIN_BUTTON_XPATH,
    LOGIN_FORM_WAIT,
    NAME_INPUT_FALLBACK,
    NAME_INPUT_XPATH,
    NETWORK_IDLE_TIMEOUT,
    OTP_INPUT_FALLBACK,
    OTP_INPUT_XPATH,
    OTP_SUBMIT_XPATH,
    PAGE_LOAD_TIMEOUT,
    SUBMIT_BUTTON_FALLBACK,
    random_age,
    random_name,
)


def _log(msg: str, log_fn: Callable[[str], None]) -> None:
    log_fn(f"[ChatGPT2 Browser] {msg}")


def _safe_xpath(page: Page, xpath: str) -> bool:
    """检查 xpath 元素是否存在且可见。"""
    try:
        el = page.locator(f"xpath={xpath}").first
        return el.is_visible(timeout=3000)
    except Exception:
        return False


def _wait_for_url_contains(page: Page, substring: str, timeout: int = PAGE_LOAD_TIMEOUT) -> bool:
    """等待 URL 包含指定子串。"""
    try:
        page.wait_for_url(f"**{substring}**", timeout=timeout * 1000)
        return True
    except PlaywrightTimeout:
        return False


def _extract_cookies(page: Page) -> dict[str, str]:
    """提取当前浏览器上下文所有 cookie。"""
    return {c["name"]: c["value"] for c in page.context.cookies()}


def _extract_session_token(cookies: dict[str, str]) -> str:
    """从 cookies 中提取 session token。"""
    return cookies.get("__Secure-next-auth.session-token", "")


def _extract_access_token(page: Page) -> str:
    """通过 chatgpt.com/api/auth/session 获取 access_token。"""
    try:
        resp = page.evaluate("""
            async () => {
                const r = await fetch('/api/auth/session');
                if (!r.ok) return null;
                return await r.json();
            }
        """)
        if resp and isinstance(resp, dict):
            return resp.get("accessToken", "") or ""
    except Exception:
        pass
    return ""


def _extract_account_id(page: Page) -> str:
    """从 localStorage 或 cookie 提取 account id。"""
    try:
        # 尝试 localStorage
        raw = page.evaluate("() => localStorage.getItem('_account')")
        if raw:
            return str(raw).strip('"')
    except Exception:
        pass
    # fallback: cookie
    cookies = _extract_cookies(page)
    return cookies.get("_account", "")


class ChatGPT2BrowserRegister:
    """ChatGPT2 浏览器注册 worker。

    由 BrowserRegistrationFlow 注入 otp_callback（邮箱轮询回调），
    worker 在需要验证码时调用 self.otp_callback() 同步等待返回。
    """

    def __init__(
        self,
        *,
        headless: bool,
        proxy: Optional[str] = None,
        otp_callback: Optional[Callable[[], str]] = None,
        log_fn: Callable[[str], None] = print,
    ):
        self.headless = headless
        self.proxy = proxy
        self.otp_callback = otp_callback
        self.log_fn = log_fn

    # ── public API ──────────────────────────────────────────────────────
    def run(self, email: str, password: str) -> dict:
        """执行完整浏览器注册流程，返回结果 dict。"""
        _log(f"启动浏览器: email={email}, headless={self.headless}", self.log_fn)

        launch_opts: dict = {"headless": self.headless}
        if self.proxy:
            launch_opts["proxy"] = {"server": self.proxy}
            launch_opts["geoip"] = True

        with Camoufox(**launch_opts) as browser:
            page: Page = browser.new_page()
            page.set_default_timeout(PAGE_LOAD_TIMEOUT * 1000)

            # 静默处理页面 JS 错误，避免 Camoufox 因 pageError.location 为 undefined 而崩溃
            page.on("pageerror", lambda err: None)

            try:
                # ── 1. 访问 chatgpt.com ──────────────────────────────
                _log("1. 访问 chatgpt.com...", self.log_fn)
                page.goto(CHATGPT_APP, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT * 1000)
                except PlaywrightTimeout:
                    _log("networkidle 超时，继续执行", self.log_fn)

                _log("页面及 XHR 请求加载完成", self.log_fn)

                # ── 2. 点击登录按钮 ───────────────────────────────────
                _log("2. 点击登录按钮...", self.log_fn)
                self._click_login_button(page)

                # ── 3. 等待 10s ───────────────────────────────────────
                _log(f"3. 等待 {LOGIN_FORM_WAIT}s...", self.log_fn)
                time.sleep(LOGIN_FORM_WAIT)

                # ── 4. 等待登录表单 ───────────────────────────────────
                _log("4. 等待登录表单...", self.log_fn)
                self._wait_for_form(page)

                # ── 5. 填写邮箱并提交 ─────────────────────────────────
                _log(f"5. 填写邮箱 {email} 并提交...", self.log_fn)
                self._fill_email_and_submit(page, email)

                # ── 6. 等待跳转到 email-verification ──────────────────
                _log("6. 等待跳转到 email-verification...", self.log_fn)
                if not _wait_for_url_contains(page, EMAIL_VERIFICATION_URL):
                    _log(f"未跳转到 {EMAIL_VERIFICATION_URL}，当前: {page.url}", self.log_fn)
                    # 也可能已经在正确的页面
                try:
                    page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT * 1000)
                except PlaywrightTimeout:
                    pass

                # ── 7. 等待 OTP 输入框并填写 ──────────────────────────
                _log("7. 等待 OTP 输入框...", self.log_fn)
                self._fill_otp(page)

                # ── 8. 提交 OTP ───────────────────────────────────────
                _log("8. 提交 OTP...", self.log_fn)
                self._click_otp_submit(page)

                # ── 9. 等待跳转到 about-you ──────────────────────────
                _log("9. 等待跳转到 about-you...", self.log_fn)
                if not _wait_for_url_contains(page, ABOUT_YOU_URL):
                    _log(f"未跳转到 {ABOUT_YOU_URL}，当前: {page.url}", self.log_fn)
                try:
                    page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT * 1000)
                except PlaywrightTimeout:
                    pass

                # ── 10. 填写姓名 + 年龄并提交 ─────────────────────────
                name = random_name()
                age = random_age()
                _log(f"10. 填写姓名={name}, 年龄={age} 并提交...", self.log_fn)
                self._fill_about_you_and_submit(page, name, age)

                # ── 11. 等待跳回 chatgpt.com ─────────────────────────
                _log("11. 等待跳回 chatgpt.com...", self.log_fn)
                if not _wait_for_url_contains(page, CHATGPT_APP):
                    _log(f"未跳回 chatgpt.com，当前: {page.url}", self.log_fn)
                try:
                    page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT * 1000)
                except PlaywrightTimeout:
                    pass

                # ── 12. OAuth 授权码流程获取 refresh_token ────────────
                _log("12. OAuth 授权码流程...", self.log_fn)
                try:
                    oauth_tokens = self._acquire_oauth_tokens(page)
                except Exception as e:
                    _log(f"  OAuth 流程异常，回退到仅 session_token: {e}", self.log_fn)
                    oauth_tokens = {"access_token": "", "refresh_token": "", "id_token": "", "expires_in": 0}

                # ── 13. 收集 token / cookie ──────────────────────────
                _log("13. 收集 cookies / token...", self.log_fn)
                time.sleep(2)

                cookies = _extract_cookies(page)
                session_token = _extract_session_token(cookies)
                access_token = oauth_tokens.get("access_token") or _extract_access_token(page)
                refresh_token = oauth_tokens.get("refresh_token", "")
                id_token = oauth_tokens.get("id_token", "")
                account_id = _extract_account_id(page)

                _log(f"  session_token: {'✓' if session_token else '✗'}", self.log_fn)
                _log(f"  access_token: {'✓' if access_token else '✗'}", self.log_fn)
                _log(f"  refresh_token: {'✓' if refresh_token else '✗'}", self.log_fn)
                _log(f"  account_id: {account_id or '✗'}", self.log_fn)
                _log(f"  cookies: {len(cookies)} 条", self.log_fn)

                return {
                    "email": email,
                    "password": password,
                    "account_id": account_id,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "id_token": id_token,
                    "session_token": session_token,
                    "workspace_id": "",
                    "cookies": json.dumps(cookies, ensure_ascii=False),
                    "profile": {},
                }

            finally:
                pass

    # ── 内部步骤方法 ───────────────────────────────────────────────────────

    def _acquire_oauth_tokens(self, page: Page) -> dict:
        """通过 HTTP（curl_cffi）执行 OAuth 授权码流程，获取 refresh_token。

        不依赖浏览器导航，直接用已登录的 session cookie 发 HTTP 请求完成授权。
        返回 {"access_token", "refresh_token", "id_token", "expires_in"}。
        """
        from curl_cffi import requests as cffi_requests

        # 从浏览器提取 session cookie
        cookies = _extract_cookies(page)
        session_token = _extract_session_token(cookies)
        if not session_token:
            _log("  无 session_token，跳过 OAuth", self.log_fn)
            return {"access_token": "", "refresh_token": "", "id_token": "", "expires_in": 0}

        oauth = _generate_oauth_params()
        auth_url = oauth["auth_url"]
        code_verifier = oauth["code_verifier"]

        _log("  HTTP OAuth 授权码流程...", self.log_fn)

        # 创建带 session cookie 的 curl_cffi session
        s = cffi_requests.Session(impersonate="chrome124", proxy=self.proxy)
        s.cookies.set(
            "__Secure-next-auth.session-token", session_token,
            domain=".chatgpt.com", path="/",
        )
        # 也带上其他关键 cookies
        for name in ("__Secure-next-auth.session-token.0", "__Secure-next-auth.session-token.1",
                      "_account", "oai-did", "cf_clearance"):
            if name in cookies:
                s.cookies.set(name, cookies[name], domain=".chatgpt.com", path="/")

        # Step 1: 手动跟随 OAuth 重定向链，直到回调到 localhost:1455 拿到 code
        code = None
        next_url = auth_url
        headers = {
            "accept": "text/html,application/xhtml+xml",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        }
        for _ in range(5):  # 最多跟 5 次重定向
            try:
                resp = s.get(next_url, headers=headers, allow_redirects=False, timeout=30)
            except Exception as e:
                _log(f"  OAuth 请求异常: {e}", self.log_fn)
                break

            if resp.status_code in (302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                if not location:
                    break
                # 检查是否已经到 localhost 回调（带 code）
                code = _extract_code_from_url(location)
                if code:
                    _log("  从重定向链获得授权码", self.log_fn)
                    break
                # 继续跟随
                next_url = location if location.startswith("http") else f"https://auth.openai.com{location}"
            else:
                _log(f"  OAuth 非重定向响应 (status={resp.status_code})", self.log_fn)
                break

        if not code:
            _log(f"  未获取到 OAuth code", self.log_fn)
            return {"access_token": "", "refresh_token": "", "id_token": "", "expires_in": 0}

        _log(f"  授权码获取成功", self.log_fn)

        # Step 2: 交换 token
        try:
            tokens = _exchange_code_for_tokens(code, code_verifier, proxy=self.proxy)
            _log("  OAuth token 交换成功", self.log_fn)
            return tokens
        except Exception as e:
            _log(f"  OAuth token 交换失败: {e}", self.log_fn)
            return {"access_token": "", "refresh_token": "", "id_token": "", "expires_in": 0}

    def _click_login_button(self, page: Page) -> None:
        """点击登录按钮。首先尝试用户指定的 xpath，失败则用文本匹配。"""
        try:
            page.locator(f"xpath={LOGIN_BUTTON_XPATH}").first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已点击登录按钮 (xpath)", self.log_fn)
        except Exception:
            _log("  xpath 登录按钮未命中，尝试文本匹配...", self.log_fn)
            try:
                page.locator('button:has-text("Log in"), button:has-text("Login"), button:has-text("登录"), button:has-text("Sign in")').first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
                _log("  已点击登录按钮 (文本匹配)", self.log_fn)
            except Exception as e:
                raise RuntimeError(f"未找到登录按钮: {e}")

    def _wait_for_form(self, page: Page) -> None:
        """等待登录表单出现。"""
        try:
            page.locator(f"xpath={EMAIL_FORM_XPATH}").first.wait_for(
                state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000
            )
            _log("  登录表单已出现 (xpath)", self.log_fn)
            return
        except PlaywrightTimeout:
            _log("  xpath 表单未命中，等待 fallback...", self.log_fn)

        # fallback: 等待邮箱输入框出现
        try:
            page.locator(EMAIL_INPUT_FALLBACK).first.wait_for(
                state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000
            )
            _log("  登录表单已出现 (fallback)", self.log_fn)
        except PlaywrightTimeout as e:
            raise RuntimeError(f"登录表单未出现: {e}")

    def _fill_email_and_submit(self, page: Page, email: str) -> None:
        """填写邮箱并点击提交。"""
        # 尝试 xpath
        try:
            el = page.locator(f"xpath={EMAIL_INPUT_XPATH}").first
            el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            el.fill(email)
            _log("  邮箱已填入 (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath 邮箱输入框未命中，使用 fallback...", self.log_fn)
            el = page.locator(EMAIL_INPUT_FALLBACK).first
            el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            el.fill(email)
            _log("  邮箱已填入 (fallback)", self.log_fn)

        # 提交
        try:
            page.locator(f"xpath={EMAIL_SUBMIT_XPATH}").first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已点击提交按钮 (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath 提交按钮未命中，使用 fallback...", self.log_fn)
            page.locator(SUBMIT_BUTTON_FALLBACK).first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已点击提交按钮 (fallback)", self.log_fn)

    def _fill_otp(self, page: Page) -> None:
        """等待 OTP 输入框出现，调用邮箱回调获取验证码并填入。"""
        # 等待 OTP 输入框
        otp_el = None
        try:
            otp_el = page.locator(f"xpath={OTP_INPUT_XPATH}").first
            otp_el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  OTP 输入框已出现 (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath OTP 输入框未命中，使用 fallback...", self.log_fn)
            try:
                otp_el = page.locator(OTP_INPUT_FALLBACK).first
                otp_el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
                _log("  OTP 输入框已出现 (fallback)", self.log_fn)
            except PlaywrightTimeout:
                # 可能页面有多个 digit input 框，尝试逐个填
                _log("  尝试多 digit input 模式...", self.log_fn)
                self._fill_otp_multi_digit(page)
                return

        # 获取验证码
        if self.otp_callback is None:
            raise RuntimeError("未提供 otp_callback，无法获取验证码")

        _log("  等待邮箱验证码...", self.log_fn)
        code = self.otp_callback()
        _log(f"  验证码: {code}", self.log_fn)

        if code and otp_el:
            otp_el.fill(code)
            _log("  OTP 已填入", self.log_fn)

    def _fill_otp_multi_digit(self, page: Page) -> None:
        """处理 6 个独立 digit input 的 OTP 表单。"""
        code = self.otp_callback() if self.otp_callback else ""
        if not code:
            raise RuntimeError("未获取到验证码")

        _log(f"  验证码: {code}", self.log_fn)
        digits = list(code)
        # 尝试找到所有 type=tel 或 inputmode=numeric 的 input
        inputs = page.locator('input[inputmode="numeric"], input[type="tel"], input[type="number"]')
        count = inputs.count()
        if count >= len(digits):
            for i, digit in enumerate(digits[:count]):
                inputs.nth(i).fill(digit)
            _log(f"  OTP 已填入 {len(digits)} 个 digit input", self.log_fn)
        else:
            # fallback: 找第一个输入框填入完整验证码
            page.locator(OTP_INPUT_FALLBACK).first.fill(code)
            _log("  OTP 已填入 (single input fallback)", self.log_fn)

    def _click_otp_submit(self, page: Page) -> None:
        """点击 OTP 提交按钮。"""
        try:
            page.locator(f"xpath={OTP_SUBMIT_XPATH}").first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已提交 OTP (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath OTP 提交按钮未命中，使用 fallback...", self.log_fn)
            page.locator(SUBMIT_BUTTON_FALLBACK).first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已提交 OTP (fallback)", self.log_fn)

    def _fill_about_you_and_submit(self, page: Page, name: str, age: int) -> None:
        """填写姓名和年龄，然后提交。"""
        # 姓名
        try:
            el = page.locator(f"xpath={NAME_INPUT_XPATH}").first
            el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            el.fill(name)
            _log(f"  姓名已填入: {name} (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath 姓名输入框未命中，使用 fallback...", self.log_fn)
            try:
                el = page.locator(NAME_INPUT_FALLBACK).first
                el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
                el.fill(name)
                _log(f"  姓名已填入: {name} (fallback)", self.log_fn)
            except PlaywrightTimeout as e:
                raise RuntimeError(f"未找到姓名输入框: {e}")

        # 年龄
        try:
            el = page.locator(f"xpath={AGE_INPUT_XPATH}").first
            el.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            el.fill(str(age))
            _log(f"  年龄已填入: {age} (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath 年龄输入框未命中，使用 fallback...", self.log_fn)
            # 找第二个 input（在姓名 input 之后）
            try:
                inputs = page.locator('input[type="text"], input:not([type])')
                if inputs.count() >= 2:
                    inputs.nth(1).fill(str(age))
                    _log(f"  年龄已填入: {age} (fallback nth)", self.log_fn)
                else:
                    raise RuntimeError("未找到年龄输入框")
            except Exception as e:
                raise RuntimeError(f"未找到年龄输入框: {e}")

        # 提交
        try:
            page.locator(f"xpath={ABOUT_YOU_SUBMIT_XPATH}").first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已提交 about-you (xpath)", self.log_fn)
        except PlaywrightTimeout:
            _log("  xpath about-you 提交按钮未命中，使用 fallback...", self.log_fn)
            page.locator(SUBMIT_BUTTON_FALLBACK).first.click(timeout=ELEMENT_WAIT_TIMEOUT * 1000)
            _log("  已提交 about-you (fallback)", self.log_fn)
