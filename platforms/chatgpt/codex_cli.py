"""Codex CLI 登录工具 —— 注册完成后自动登录 Codex CLI 并存库"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# 项目根目录下的 codex_home 基础路径
CODEX_HOME_BASE = Path(__file__).resolve().parent.parent.parent / "codex_home"


def _log(msg: str, log_fn: Callable[[str], None] | None = None) -> None:
    """同时输出到 log_fn（任务日志）和 logger（服务日志）。"""
    if log_fn:
        log_fn(f"[Codex CLI] {msg}")
    logger.info("login_codex_cli: %s", msg)


def login_codex_cli(
    access_token: str,
    account_id: str,
    *,
    log_fn: Callable[[str], None] | None = None,
) -> dict | None:
    """
    使用 access_token 登录 Codex CLI，返回 auth.json 内容。

    流程：
    1. 检查 codex CLI 是否可用
    2. 创建临时 CODEX_HOME 目录
    3. 执行 ``codex login --with-access-token``（token 通过 stdin 传入）
    4. 读取生成的 ``auth.json``
    5. 清理临时目录，返回 auth.json 内容

    Args:
        access_token: ChatGPT 的 access_token
        account_id: ChatGPT 的 account_id（用于命名临时目录）
        log_fn: 可选的任务日志回调，用于前端实时显示

    Returns:
        auth.json 的 JSON 内容（dict），失败返回 None
    """
    if not access_token:
        _log("access_token 为空，跳过 Codex CLI 登录", log_fn)
        return None

    # 检查 codex CLI 是否在 PATH 中
    _log("检查 codex CLI 可用性...", log_fn)
    codex_bin = shutil.which("codex")
    if not codex_bin:
        _log("codex CLI 未安装或不在 PATH 中，跳过", log_fn)
        return None
    _log(f"codex CLI 路径: {codex_bin}", log_fn)

    # 为每个 account_id 创建独立临时目录
    codex_home = CODEX_HOME_BASE / account_id
    codex_home.mkdir(parents=True, exist_ok=True)
    auth_json_path = codex_home / "auth.json"

    _log(f"临时 CODEX_HOME: {codex_home}", log_fn)

    # 确保是干净的目录（删除可能残留的旧 auth.json）
    if auth_json_path.exists():
        auth_json_path.unlink()
        _log("已删除旧的 auth.json", log_fn)

    try:
        # 设置 CODEX_HOME 环境变量（仅对子进程生效）
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home.resolve())

        _log("执行 codex login --with-access-token ...", log_fn)

        result = subprocess.run(
            [codex_bin, "login", "--with-access-token"],
            input=access_token,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        stdout_text = (result.stdout or "").strip()
        stderr_text = (result.stderr or "").strip()

        _log(f"  exit code: {result.returncode}", log_fn)
        if stdout_text:
            for line in stdout_text.splitlines():
                _log(f"  stdout: {line}", log_fn)
        if stderr_text:
            for line in stderr_text.splitlines():
                _log(f"  stderr: {line}", log_fn)

        if result.returncode != 0:
            detail = stderr_text or stdout_text or "unknown error"
            _log(f"codex login 失败 (rc={result.returncode}): {detail}", log_fn)
            return None

        _log("codex login 命令执行成功", log_fn)

        # 检查 auth.json 是否生成
        if not auth_json_path.exists():
            _log(f"auth.json 未生成于 {auth_json_path}", log_fn)
            return None

        _log(f"读取 auth.json ({auth_json_path})", log_fn)

        # 读取 auth.json 内容
        with open(auth_json_path, "r", encoding="utf-8") as f:
            auth_data = json.load(f)

        keys = list(auth_data.keys()) if isinstance(auth_data, dict) else []
        _log(f"auth.json 内容: ({', '.join(keys)})", log_fn)

        return auth_data

    except subprocess.TimeoutExpired:
        _log("codex login 超时（30s）", log_fn)
        return None
    except FileNotFoundError:
        _log("找不到 codex 可执行文件", log_fn)
        return None
    except json.JSONDecodeError as exc:
        _log(f"auth.json 解析失败: {exc}", log_fn)
        return None
    except Exception as exc:
        _log(f"未预期的异常: {exc}", log_fn)
        return None
    finally:
        # 清理临时 CODEX_HOME 目录，释放磁盘空间
        try:
            if codex_home.exists():
                shutil.rmtree(codex_home, ignore_errors=True)
                _log("已清理临时 CODEX_HOME", log_fn)
        except Exception:
            pass
