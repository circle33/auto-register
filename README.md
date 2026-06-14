# gpt-auto-register

ChatGPT 自动化账号注册 · 协议 / 浏览器双模式 · Python FastAPI + React

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLModel (SQLite) |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix UI |
| 浏览器 | Playwright + Camoufox + Patchright |
| HTTP | curl_cffi (TLS 指纹伪装) |

## 项目结构

```
├── main.py                 # FastAPI 入口 + SPA fallback
├── api/                    # HTTP 路由层
├── application/            # 应用服务层
├── domain/                 # 领域模型 (slots dataclasses)
├── infrastructure/         # SQLModel 仓储
├── core/                   # 平台基类、auth、captcha、mailbox、scheduler
├── platforms/chatgpt/      # ChatGPT 平台插件 (唯一平台)
├── providers/              # captcha / mailbox / proxy / sms 驱动
├── services/               # turnstile solver、task runtime
├── frontend/               # Vite + React SPA → static/
├── customer_portal_api/    # C 端独立 API
└── tests/                  # pytest
```

## 快速开始

```bash
git clone <repo-url> gpt-auto-register && cd gpt-auto-register

# Python 后端
uv sync
uv run python main.py                    # :8000

# 前端开发
pnpm --prefix frontend dev               # :5173
pnpm --prefix frontend build             # tsc + vite → static/

# 测试
uv run pytest
```

## 常用命令

```bash
uv sync                                  # 安装 Python 依赖
uv run python main.py                    # 启动后端
uv run pytest                            # 运行测试
pnpm --prefix frontend dev               # Vite 开发服务器
pnpm --prefix frontend build             # 构建前端
pnpm --prefix frontend lint              # ESLint
```

## Docker

```bash
docker build --build-arg APP_VERSION=1.0.0 -t gpt-auto-register .
docker run -p 8000:8000 -e APP_PASSWORD=xxx gpt-auto-register
```

## 注意事项

- `static/` 是前端构建产物，不要手动编辑
- `core/version.py` 由 Dockerfile 构建时注入 `APP_VERSION`
- `.env` 已 gitignore，直接使用环境变量
- `conftest.py` 在 app import 前替换 DB engine 为临时 SQLite
- `platforms/` 仅保留 ChatGPT；`reference/` 为原始多平台参考代码
