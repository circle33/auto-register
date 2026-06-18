"""Chat2API Proxy API — OpenAI-compatible endpoints powered by gpt2 accounts."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from core.account_graph import load_account_graphs
from core.config_store import config_store
from core.db import AccountModel, engine
from services.chat2api_proxy import (
    chat_completion_stream,
    chat_completion_sync,
    list_models,
    NoAccountError,
    ProxyError,
)

router = APIRouter(tags=["v1"])


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict] = ""


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    stream: bool = True
    temperature: float | None = None
    max_tokens: int | None = None


def _verify_api_key(request: Request) -> None:
    """Verify API key if proxy auth is enabled."""
    from core.config_store import config_store
    enabled = config_store.get("chat2api_enabled", "false").lower() == "true"
    if not enabled:
        raise HTTPException(503, "Chat2API proxy is not enabled")
    api_key = config_store.get("chat2api_api_key", "")
    if api_key:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {api_key}":
            raise HTTPException(401, "Invalid API key")


@router.get("/v1/models")
def get_models(request: Request):
    _verify_api_key(request)
    return list_models()


@router.get("/v1/models/{model:path}")
def get_model(model: str, request: Request):
    _verify_api_key(request)
    model_data = next((m for m in list_models()["data"] if m["id"] == model), None)
    if not model_data:
        raise HTTPException(404, f"Model {model} not found")
    return model_data


@router.post("/v1/chat/completions")
def chat_completions(body: ChatCompletionRequest, request: Request):
    _verify_api_key(request)

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    try:
        if body.stream:
            async def generate():
                try:
                    async for chunk in chat_completion_stream(messages, body.model):
                        yield chunk
                except NoAccountError as exc:
                    error = {"error": {"message": str(exc), "type": "no_account"}}
                    yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except ProxyError as exc:
                    error = {"error": {"message": str(exc), "type": "proxy_error"}}
                    yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            result = chat_completion_sync(messages, body.model)
            return result

    except NoAccountError as exc:
        raise HTTPException(503, str(exc))
    except ProxyError as exc:
        raise HTTPException(502, str(exc))


@router.get("/api/chat2api/status")
async def get_proxy_status(request: Request):
    """Chat2API proxy status — enabled state, available accounts."""
    enabled = config_store.get("chat2api_enabled", "false").lower() == "true"
    api_key_configured = bool(config_store.get("chat2api_api_key", ""))

    accounts = []
    with Session(engine) as session:
        db_accounts = session.exec(
            select(AccountModel)
            .where(AccountModel.platform == "chatgpt2")
            .order_by(AccountModel.created_at.desc())
            .limit(500)
        ).all()
        graphs = load_account_graphs(session, [int(a.id) for a in db_accounts if a.id])

    active_statuses = {"registered", "trial", "subscribed"}
    for acc in db_accounts:
        graph = graphs.get(int(acc.id or 0), {})
        lifecycle = graph.get("lifecycle_status", "unknown")
        credentials_list = graph.get("credentials", [])
        credentials: dict[str, str] = {}
        for c in credentials_list:
            if c.get("scope") == "platform":
                k = c.get("key", "")
                v = c.get("value", "")
                if k and v:
                    # Truncate token previews
                    if k.endswith("token") and len(v) > 12:
                        credentials[k] = v[:8] + "..." + v[-4:]
                    else:
                        credentials[k] = v

        accounts.append({
            "id": acc.id,
            "email": acc.email,
            "lifecycle": lifecycle,
            "active": lifecycle in active_statuses,
            "has_access_token": bool(credentials.get("access_token")),
            "credentials": credentials,
        })

    active_count = sum(1 for a in accounts if a["active"] and a["has_access_token"])

    return {
        "enabled": enabled,
        "api_key_configured": api_key_configured,
        "total_accounts": len(accounts),
        "active_accounts": active_count,
        "accounts": accounts,
    }


@router.post("/api/chat2api/refresh-cookies")
def refresh_cookies(request: Request):
    """刷新所有 gpt2 账号的 cookies"""
    results = []
    with Session(engine) as session:
        accounts = session.exec(
            select(AccountModel)
            .where(AccountModel.platform == "chatgpt2")
            .limit(50)
        ).all()

    for acc in accounts:
        try:
            class _A:
                pass
            a = _A()
            a.email = acc.email
            a.user_id = str(acc.id)
            a.token = ""
            a.status = None
            a.trial_end_time = 0
            a.region = ""
            a.extra = {}
            graphs = load_account_graphs(session, [int(acc.id)])
            graph = graphs.get(int(acc.id), {})
            for c in graph.get("credentials", []):
                if c.get("scope") == "platform":
                    a.extra[c["key"]] = c["value"]

            from platforms.chatgpt2.plugin import ChatGPT2Platform
            from core.base_platform import RegisterConfig
            platform = ChatGPT2Platform(config=RegisterConfig(executor_type="headless"))
            result = platform._handle_refresh_cookies(a, {})
            results.append({"email": acc.email, **result})
        except Exception as e:
            results.append({"email": acc.email, "ok": False, "error": str(e)})

    return {"refreshed": len(results), "results": results}
