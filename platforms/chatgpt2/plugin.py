"""ChatGPT2 浏览器注册平台插件。"""
from core.base_platform import BasePlatform, Account, AccountStatus, RegisterConfig
from core.base_mailbox import BaseMailbox
from core.registration import (
    BrowserRegistrationAdapter,
    BrowserRegistrationFlow,
    OtpSpec,
    RegistrationCapability,
    RegistrationContext,
    RegistrationResult,
)
from core.registry import register


@register
class ChatGPT2Platform(BasePlatform):
    name = "chatgpt2"
    display_name = "ChatGPT2"
    version = "1.0.0"
    supported_executors = ["headless", "headed"]
    supported_identity_modes = ["mailbox"]
    supported_oauth_providers = []

    capabilities = [
        "query_state",
        "refresh_token",
    ]

    def __init__(self, config: RegisterConfig = None, mailbox: BaseMailbox = None):
        super().__init__(config)
        self.mailbox = mailbox

    # ── 有效性检查 ─────────────────────────────────────────────────────
    def check_valid(self, account: Account) -> bool:
        """检查账号是否有效（复用 ChatGPT 平台的订阅状态检测）。"""
        self._last_check_overview = {}
        try:
            from platforms.chatgpt.payment import fetch_subscription_status_details

            class _A:
                pass

            a = _A()
            extra = account.extra or {}
            a.access_token = extra.get("access_token") or account.token
            a.id_token = extra.get("id_token", "")
            a.cookies = extra.get("cookies", "")
            a.extra = extra

            proxy = self.config.proxy if self.config else None
            details = fetch_subscription_status_details(a, proxy=proxy)
            status = details.get("status")
            overview = {
                "plan": status,
                "plan_name": status,
                "check_source": details.get("source"),
            }
            if isinstance(details.get("usage"), dict):
                overview["chatgpt_usage"] = details["usage"]
            self._last_check_overview = overview
            return status not in ("expired", "invalid", "banned", None)
        except Exception:
            return False

    def get_last_check_overview(self) -> dict:
        return dict(getattr(self, "_last_check_overview", {}) or {})

    # ── 浏览器注册适配器 ─────────────────────────────────────────────────
    def build_browser_registration_adapter(self):
        return BrowserRegistrationAdapter(
            result_mapper=self._map_result,
            browser_worker_builder=self._build_worker,
            browser_register_runner=self._run_worker,
            capability=RegistrationCapability(
                browser_mailbox_requires_email=True,
                browser_mailbox_requires_mailbox=True,
            ),
            otp_spec=OtpSpec(
                wait_message="等待邮箱验证码...",
                timeout=120,
            ),
        )

    def _build_worker(self, ctx: RegistrationContext, artifacts):
        from platforms.chatgpt2.browser_register import ChatGPT2BrowserRegister

        return ChatGPT2BrowserRegister(
            headless=(ctx.executor_type == "headless"),
            proxy=ctx.proxy,
            otp_callback=artifacts.otp_callback,
            log_fn=ctx.log,
        )

    def _run_worker(self, worker, ctx: RegistrationContext, artifacts):
        return worker.run(
            email=ctx.identity.email or ctx.email or "",
            password=ctx.password or "",
        )

    def _map_result(self, ctx: RegistrationContext, raw: dict) -> RegistrationResult:
        """将浏览器 worker 返回的 dict 映射为 RegistrationResult。"""
        return RegistrationResult(
            email=raw.get("email", "") or (ctx.identity.email or ""),
            password=raw.get("password", "") or (ctx.password or ""),
            user_id=raw.get("account_id", ""),
            token=raw.get("access_token", ""),
            status=AccountStatus.REGISTERED,
            extra={
                "access_token": raw.get("access_token", ""),
                "refresh_token": raw.get("refresh_token", ""),
                "id_token": raw.get("id_token", ""),
                "session_token": raw.get("session_token", ""),
                "workspace_id": raw.get("workspace_id", ""),
                "cookies": raw.get("cookies", ""),
                "profile": raw.get("profile", {}),
            },
        )

    # ── 平台操作 ─────────────────────────────────────────────────────────
    def get_platform_actions(self) -> list:
        # 沿用 capability 系统生成 actions，保持与 capabilities 声明一致
        return self.get_capability_actions()

    def _handle_query_state(self, account: Account, params: dict) -> dict:
        """查询账号状态 — 复用 ChatGPT 平台的完整查询。"""
        extra = account.extra or {}
        proxy = self.config.proxy if self.config else None
        from platforms.chatgpt.switch import fetch_chatgpt_account_state

        data = fetch_chatgpt_account_state(
            access_token=extra.get("access_token") or account.token,
            session_token=extra.get("session_token", ""),
            cookies=extra.get("cookies", ""),
            proxy=proxy,
        )
        return {"ok": True, "data": data}

    def _handle_refresh_token(self, account: Account, params: dict) -> dict:
        """刷新 Token — 复用 ChatGPT 平台的 TokenRefreshManager。"""
        import json as _json

        extra = account.extra or {}
        proxy = self.config.proxy if self.config else None

        # session_token 可能在 extra 里，也可能嵌在 cookies JSON 里
        session_token = extra.get("session_token", "")
        if not session_token:
            cookies_raw = extra.get("cookies", "")
            if cookies_raw:
                try:
                    cookies_dict = _json.loads(cookies_raw) if isinstance(cookies_raw, str) else cookies_raw
                    for key, val in cookies_dict.items():
                        if key.startswith("__Secure-next-auth.session-token"):
                            session_token = str(val or "")
                            break
                except (_json.JSONDecodeError, TypeError):
                    pass

        class _A:
            pass

        a = _A()
        a.email = account.email
        a.access_token = extra.get("access_token") or account.token
        a.refresh_token = extra.get("refresh_token", "")
        a.session_token = session_token
        a.cookies = extra.get("cookies", "")
        a.client_id = extra.get("client_id", "")

        from platforms.chatgpt.token_refresh import TokenRefreshManager

        manager = TokenRefreshManager(proxy_url=proxy)
        result = manager.refresh_account(a)
        if result.success:
            return {"ok": True, "data": {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
            }}
        return {"ok": False, "error": result.error_message}

    def _execute_platform_action(self, action_id: str, account: Account, params: dict) -> dict:
        # 所有标准 action 已通过 _handle_* 覆盖，这里只处理自定义
        raise NotImplementedError(f"Unknown action: {action_id}")
