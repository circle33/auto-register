@echo off
REM gpt-auto-register 启动脚本 (Windows)
REM   start h  — 启动后端
REM   start q  — 启动前端

if "%1"=="h" goto backend
if "%1"=="q" goto frontend
echo 用法: start ^<h^|q^>
echo   h  启动后端 (FastAPI :8000^)
echo   q  启动前端 (Vite :5173^)
exit /b 1

:backend
echo [start] 启动后端...
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
goto :eof

:frontend
echo [start] 启动前端...
pnpm --dir frontend run dev
goto :eof
