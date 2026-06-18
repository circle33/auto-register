"""Chat2API Proxy — exposes gpt2 accounts as OpenAI-compatible API via browser."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from sqlmodel import Session, select

from core.account_graph import load_account_graphs
from core.clash_proxy import clash_proxy
from core.db import AccountModel, engine

logger = logging.getLogger(__name__)

MODEL_LIST = [
    {"id": "gpt-5.5", "object": "model", "owned_by": "openai"},
]


class ProxyError(Exception):
    pass


class NoAccountError(ProxyError):
    pass


def _select_account() -> tuple[AccountModel, dict]:
    with Session(engine) as session:
        accounts = session.exec(
            select(AccountModel)
            .where(AccountModel.platform == "chatgpt2")
            .order_by(AccountModel.created_at.desc())
            .limit(200)
        ).all()

    active_statuses = {"registered", "trial", "subscribed"}
    with Session(engine) as session:
        graphs = load_account_graphs(session, [int(a.id) for a in accounts if a.id])

    for acc in accounts:
        graph = graphs.get(int(acc.id or 0), {})
        if graph.get("lifecycle_status") not in active_statuses:
            continue
        credentials = {
            c["key"]: c["value"]
            for c in (graph.get("credentials") or [])
            if c.get("scope") == "platform"
        }
        cookies_raw = credentials.get("cookies", "")
        if not cookies_raw:
            continue
        try:
            cookies = json.loads(cookies_raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not cookies:
            continue
        return acc, {"cookies": cookies, "credentials": credentials}

    raise NoAccountError("no active gpt2 account with cookies found")


def _get_proxy_url() -> str | None:
    try:
        connected, _ = clash_proxy.test_connection()
        if connected and clash_proxy.check_proxy_port():
            return clash_proxy.get_proxy_url()
    except Exception:
        pass
    return None


def _build_user_prompt(messages: list[dict]) -> str:
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(
                p.get("text", "") for p in content if p.get("type") == "text"
            )
        else:
            text = str(content)
        if role == "system":
            parts.insert(0, f"[System instruction: {text}]")
        elif role == "user":
            parts.append(text)
        elif role == "assistant":
            parts.append(f"[Previous assistant response: {text}]")
    return "\n\n".join(parts)


def _chat_via_browser(email: str, cookies: dict, prompt: str, proxy_url: str | None) -> str:
    """Create browser, send message, wait for response, return text."""
    from camoufox.sync_api import Camoufox

    launch_opts: dict = {"headless": True}
    if proxy_url:
        launch_opts["proxy"] = {"server": proxy_url}
        launch_opts["geoip"] = True

    camoufox = Camoufox(**launch_opts)
    try:
        camoufox.start()
        browser = camoufox.browser
        page = browser.new_page()
        page.set_default_timeout(20000)
        page.on("pageerror", lambda err: None)

        page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
        cookie_list = [{"name": n, "value": str(v), "domain": ".chatgpt.com", "path": "/"} for n, v in cookies.items()]
        page.context.add_cookies(cookie_list)
        page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        if "/auth/login" in page.url or page.locator("#prompt-textarea").count() == 0:
            raise ProxyError("Failed to log in to ChatGPT")

        textarea = page.locator("#prompt-textarea")
        textarea.wait_for(state="visible", timeout=10000)
        textarea.fill(prompt)
        time.sleep(0.3)
        textarea.press("Enter")

        prev_text = ""
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(1)
            try:
                messages = page.locator('[data-message-author-role="assistant"]')
                count = messages.count()
                if count > 0:
                    full_text = (messages.nth(count - 1).text_content() or "").strip()
                    if full_text and full_text != prev_text:
                        prev_text = full_text
                    elif prev_text:
                        time.sleep(2)
                        messages = page.locator('[data-message-author-role="assistant"]')
                        if messages.count() > 0:
                            check = (messages.nth(messages.count() - 1).text_content() or "").strip()
                            if check == prev_text:
                                return prev_text
            except Exception:
                pass
        return prev_text or ""
    finally:
        try:
            camoufox.__exit__(None, None, None)
        except Exception:
            pass


async def chat_completion_stream(
    messages: list[dict],
    model: str = "auto",
) -> AsyncGenerator[str, None]:
    acc, account_data = _select_account()
    cookies = account_data["cookies"]
    proxy_url = _get_proxy_url()
    prompt = _build_user_prompt(messages)

    logger.info("chat2api(browser): account=%s prompt_len=%d", acc.email, len(prompt))

    try:
        content = await asyncio.to_thread(
            _chat_via_browser, acc.email or str(acc.id), cookies, prompt, proxy_url,
        )
        if not content:
            yield f"data: {json.dumps({'error': {'message': 'empty response', 'type': 'proxy_error'}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        chunk_id = f"chatcmpl-browser-{int(time.time())}"
        for i in range(0, len(content), 50):
            piece = content[i : i + 50]
            chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": piece},
                    "finish_reason": None,
                }],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        finish = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(finish, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.error("chat2api: error: %s", exc)
        yield f"data: {json.dumps({'error': {'message': str(exc), 'type': 'proxy_error'}}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


def chat_completion_sync(messages: list[dict], model: str = "auto") -> dict:
    acc, account_data = _select_account()
    cookies = account_data["cookies"]
    proxy_url = _get_proxy_url()
    prompt = _build_user_prompt(messages)

    logger.info("chat2api-sync: account=%s prompt_len=%d", acc.email, len(prompt))

    content = _chat_via_browser(acc.email or str(acc.id), cookies, prompt, proxy_url)

    return {
        "id": f"chatcmpl-browser-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def list_models() -> dict:
    return {"object": "list", "data": MODEL_LIST}
