#!/bin/bash
# gpt-auto-register 启动脚本
#   start.sh h  — 启动后端 (FastAPI + uvicorn)
#   start.sh q  — 启动前端 (Vite dev server)

set -e

case "$1" in
  h)
    echo "[start] 停掉旧后端..."
    fuser -k 8000/tcp 2>/dev/null || kill $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
    echo "[start] 启动后端..."
    uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ;;
  q)
    echo "[start] 停掉旧前端..."
    fuser -k 5173/tcp 2>/dev/null || kill $(lsof -ti:5173) 2>/dev/null || true
    sleep 1
    echo "[start] 启动前端..."
    pnpm --dir frontend run dev
    ;;
  *)
    echo "用法: start.sh <h|q>"
    echo "  h  启动后端 (FastAPI :8000)"
    echo "  q  启动前端 (Vite :5173)"
    exit 1
    ;;
esac
