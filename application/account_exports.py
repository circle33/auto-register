from __future__ import annotations

import base64
import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from core.datetime_utils import serialize_datetime
from domain.accounts import AccountExportSelection, AccountRecord
from infrastructure.accounts_repository import AccountsRepository


CHATGPT_PLATFORM = "chatgpt"
DEFAULT_CHATGPT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"


@dataclass(slots=True)
class ExportArtifact:
    filename: str
    media_type: str
    content: str | bytes | io.BytesIO


def _decode_jwt_payload(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def _isoformat(value: datetime | None) -> str | None:
    return serialize_datetime(value)


def _timestamp_name(prefix: str, suffix: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{suffix}"


def _credential_value(item: AccountRecord, *keys: str) -> str:
    for key in keys:
        for credential in item.credentials or []:
            if credential.get("scope") == "platform" and credential.get("key") == key and credential.get("value"):
                return str(credential["value"])
    return ""


def _mailbox_provider_name(item: AccountRecord) -> str:
    for resource in item.provider_resources or []:
        if resource.get("resource_type") == "mailbox" and resource.get("provider_name"):
            return str(resource["provider_name"])
    for provider_account in item.provider_accounts or []:
        if provider_account.get("provider_type") == "mailbox" and provider_account.get("provider_name"):
            return str(provider_account["provider_name"])
    return ""


def _chatgpt_auth_info(*tokens: str) -> dict:
    merged: dict = {}
    for token in tokens:
        if not token:
            continue
        payload = _decode_jwt_payload(token)
        auth_info = payload.get("https://api.openai.com/auth", {})
        if isinstance(auth_info, dict):
            for key, value in auth_info.items():
                if value not in (None, "", [], {}):
                    merged[key] = value
    return merged


def _chatgpt_export_payload(item: AccountRecord) -> dict:
    access_token = _credential_value(item, "access_token", "accessToken", "legacy_token")
    refresh_token = _credential_value(item, "refresh_token", "refreshToken")
    id_token = _credential_value(item, "id_token", "idToken")
    session_token = _credential_value(item, "session_token", "sessionToken")
    workspace_id = _credential_value(item, "workspace_id", "workspaceId")
    payload = _decode_jwt_payload(access_token) if access_token else {}
    auth_info = _chatgpt_auth_info(access_token, id_token)
    client_id = _credential_value(item, "client_id", "clientId") or str(payload.get("client_id", "") or DEFAULT_CHATGPT_CLIENT_ID)
    cookies = _credential_value(item, "cookies", "cookie")
    account_id = item.user_id or _credential_value(item, "account_id", "chatgpt_account_id") or ""
    email_service = _mailbox_provider_name(item)

    if not account_id:
        account_id = str(auth_info.get("chatgpt_account_id", "") or auth_info.get("account_id", "") or "")
    if not workspace_id:
        workspace_id = str(auth_info.get("organization_id", "") or "")
    expires_at = None
    exp_timestamp = payload.get("exp")
    if isinstance(exp_timestamp, int) and exp_timestamp > 0:
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    last_refresh_at = item.updated_at
    iat_timestamp = payload.get("iat")
    if isinstance(iat_timestamp, int) and iat_timestamp > 0:
        last_refresh_at = datetime.fromtimestamp(iat_timestamp, tz=timezone.utc)

    return {
        "id": item.id,
        "email": item.email,
        "password": item.password,
        "client_id": client_id,
        "account_id": account_id,
        "workspace_id": workspace_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "session_token": session_token,
        "cookies": cookies,
        "email_service": email_service,
        "registered_at": _isoformat(item.created_at),
        "last_refresh": _isoformat(last_refresh_at),
        "expires_at": _isoformat(expires_at),
        "status": item.display_status,
        "expires_at_unix": int(expires_at.timestamp()) if expires_at else 0,
    }


class AccountExportsService:
    def __init__(self, repository: AccountsRepository | None = None):
        self.repository = repository or AccountsRepository()

    def export_chatgpt_json(self, selection: AccountExportSelection) -> ExportArtifact:
        items = self._load_chatgpt_items(selection)
        content = json.dumps(
            [
                {
                    "email": payload["email"],
                    "password": payload["password"],
                    "client_id": payload["client_id"],
                    "account_id": payload["account_id"],
                    "workspace_id": payload["workspace_id"],
                    "access_token": payload["access_token"],
                    "refresh_token": payload["refresh_token"],
                    "id_token": payload["id_token"],
                    "session_token": payload["session_token"],
                    "email_service": payload["email_service"],
                    "registered_at": payload["registered_at"],
                    "last_refresh": payload["last_refresh"],
                    "expires_at": payload["expires_at"],
                    "status": payload["status"],
                }
                for payload in [_chatgpt_export_payload(item) for item in items]
            ],
            ensure_ascii=False,
            indent=2,
        )
        return ExportArtifact(
            filename=_timestamp_name("accounts", "json"),
            media_type="application/json",
            content=content,
        )

    def export_chatgpt_csv(self, selection: AccountExportSelection) -> ExportArtifact:
        items = self._load_chatgpt_items(selection)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Email",
                "Password",
                "Client ID",
                "Account ID",
                "Workspace ID",
                "Access Token",
                "Refresh Token",
                "ID Token",
                "Session Token",
                "Email Service",
                "Status",
                "Registered At",
                "Last Refresh",
                "Expires At",
            ]
        )
        for item in items:
            payload = _chatgpt_export_payload(item)
            writer.writerow(
                [
                    payload["id"],
                    payload["email"],
                    payload["password"],
                    payload["client_id"],
                    payload["account_id"],
                    payload["workspace_id"],
                    payload["access_token"],
                    payload["refresh_token"],
                    payload["id_token"],
                    payload["session_token"],
                    payload["email_service"],
                    payload["status"],
                    payload["registered_at"] or "",
                    payload["last_refresh"] or "",
                    payload["expires_at"] or "",
                ]
            )
        return ExportArtifact(
            filename=_timestamp_name("accounts", "csv"),
            media_type="text/csv",
            content=output.getvalue(),
        )

    def _load_chatgpt_items(self, selection: AccountExportSelection) -> list[AccountRecord]:
        selection.platform = selection.platform or CHATGPT_PLATFORM
        if selection.platform != CHATGPT_PLATFORM:
            raise ValueError("仅支持 ChatGPT 账号导出")
        return self.repository.select_for_export(selection)
