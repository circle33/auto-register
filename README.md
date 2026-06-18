# gpt-auto-register

ChatGPT2 自动化账号注册 + Chat2API 代理 · Python FastAPI + React

## 功能

- **自动注册** — Camoufox 浏览器自动化完成 ChatGPT 邮箱验证码注册全流程
- **Chat2API** — 将注册的 gpt2 账号暴露为 OpenAI 兼容 API (`/v1/chat/completions`)
- **账号管理** — 注册 / 导入 / 导出 / 状态检测 / token 刷新 / cookie 续期
- **代理服务** — Clash 集成，自动切换节点

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLModel (SQLite) |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix UI |
| 浏览器 | Playwright + Camoufox |
| HTTP | curl_cffi (TLS 指纹伪装) |

## 项目结构

```
├── main.py                     # FastAPI 入口 + SPA fallback
├── api/                        # HTTP 路由层
│   ├── chat2api_proxy.py       # Chat2API 代理 (/v1/*)
│   ├── clash.py                # Clash 代理管理
│   └── ...                     # 账号 / 任务 / 平台等路由
├── application/                # 应用服务层
├── domain/                     # 领域模型 (slots dataclasses)
├── infrastructure/             # SQLModel 仓储
├── core/                       # 平台基类、auth、captcha、mailbox、scheduler
├── platforms/
│   ├── chatgpt/                # ChatGPT 共享模块 (token refresh / switch / payment)
│   └── chatgpt2/               # ChatGPT2 浏览器注册插件
├── providers/                  # captcha / mailbox 驱动
├── services/
│   ├── chat2api_proxy.py       # Chat2API 代理核心 (浏览器操作 ChatGPT)
│   ├── task_runtime.py         # 任务调度器
│   └── ...                     # turnstile solver
├── frontend/                   # Vite + React SPA → static/
├── customer_portal_api/        # C 端独立 API
├── reference/                  # 参考 Chat2API 项目
├── tests/                      # pytest
└── start.sh                    # 启动脚本 (自动停旧启新)
```

## 快速开始

```bash
# 后端
uv sync
./start.sh h                     # :8000

# 前端
pnpm --prefix frontend dev       # :5173

# 测试
uv run pytest
```

## Chat2API

注册 gpt2 账号后，开启 Chat2API 代理：

```bash
# 启用
curl -X PUT http://localhost:8000/api/config \
  -d '{"data": {"chat2api_enabled": "true"}}'

# 模型列表
curl http://localhost:8000/v1/models

# 聊天
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"hello"}],"stream":false}'

# 刷新过期 cookies
curl -X POST http://localhost:8000/api/chat2api/refresh-cookies

# 查看状态
curl http://localhost:8000/api/chat2api/status
```

可选 API Key 保护：

```bash
curl -X PUT http://localhost:8000/api/config \
  -d '{"data": {"chat2api_api_key": "sk-your-key"}}'
# 请求携带: -H "Authorization: Bearer sk-your-key"
```

## 注意事项

- `static/` 是前端构建产物，不要手动编辑
- `core/version.py` 由 Dockerfile 构建时注入 `APP_VERSION`
- `.env` 已 gitignore，直接使用环境变量
- Chat2API 使用 Camoufox 浏览器操作 ChatGPT 页面，首次请求需 30s+ 启动浏览器
