# gpt-auto-register

## Stack

- **Backend:** Python 3.12 + FastAPI + uvicorn + SQLModel (SQLite)
- **Package manager:** uv (Python) / pnpm (Node)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix UI
- **Browser automation:** Playwright + Camoufox + Patchright
- **HTTP:** curl_cffi (TLS fingerprinting)

## Layout

- `main.py` — FastAPI app factory, lifespan hook (DB → plugins → scheduler/runtime/solver), SPA fallback
- `api/` — FastAPI routers (accounts/tasks/platforms/proxies/auth/config/health/lifecycle/providers/stats/sms/system)
- `application/` — thin orchestration between api and domain
- `domain/` — `@dataclass(slots=True)` records (AccountRecord, TaskRecord, etc.)
- `infrastructure/` — SQLModel repository classes
- `core/` — platform base classes, account graph, auth, captcha/mailbox/sms abstractions, DB init, proxy pool, registration engine, scheduler
- `platforms/chatgpt/` — only ChatGPT platform plugin: `plugin.py` + `protocol_mailbox.py` + OAuth/register/token-refresh/browser modules
- `providers/` — captcha/mailbox/proxy/sms drivers, pluggable via `registry.py`
- `services/` — turnstile solver subprocess, task runtime
- `frontend/` — Vite + React SPA, builds into `static/`
- `customer_portal_api/` — separate FastAPI service (own Docker Compose)
- `tests/` — pytest, `conftest.py` creates temp SQLite + TestClient per session
- `reference/` — original full-project reference (all 11+ platforms preserved)

## Commands

```bash
uv run python main.py                     # backend on :8000
uv run pytest                             # all tests
uv sync                                   # install Python deps

pnpm --prefix frontend dev                # Vite dev server
pnpm --prefix frontend build              # tsc + vite → ../static/
pnpm --prefix frontend lint               # eslint

docker build --build-arg APP_VERSION=1.0.0 -t gpt-auto-register .
docker run -p 8000:8000 -e APP_PASSWORD=xxx gpt-auto-register

```

## Conventions

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- **DDD-lite:** `api → application → domain` + `infrastructure` for persistence, `core` for shared logic
- **Plugin pattern:** each `platforms/<name>/` has `plugin.py` (extends `BasePlatform`, `@register`) + `protocol_mailbox.py`
- **`from __future__ import annotations`** at top of most `.py` files
- **`slots=True` dataclasses** in `domain/`
- **Tests use real temp SQLite** — `conftest.py` patches `core.db.engine` before app import

## Watch out for

- **static/ is generated** — frontend build output; don't edit by hand
- **`core/version.py` injected at build time** — Dockerfile overwrites it with `APP_VERSION`
- **`conftest.py` replaces DB engine globally** — must run before any app module imports
- **Windows encoding guard** at top of `main.py` — forces UTF-8 stdout/stderr (GBK locale crashes on emoji)
- **`.env` is gitignored** — use env vars directly or copy `customer_portal_api/.env.example`
- **Only ChatGPT platform remains** — `platforms/` contains only `chatgpt/`; `reference/` holds the original multi-platform code
