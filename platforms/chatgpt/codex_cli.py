"""Codex CLI 登录工具 —— 注册完成后自动登录 Codex CLI 并存库"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录下的 codex_home 基础路径
CODEX_HOME_BASE = Path(__file__).resolve().parent.parent.parent / "codex_home"


def login_codex_cli(access_token: str, account_id: str) -> dict | None:
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

    Returns:
        auth.json 的 JSON 内容（dict），失败返回 None
    """
    if not access_token:
        logger.warning("login_codex_cli: access_token 为空，跳过")
        return None

    # 检查 codex CLI 是否在 PATH 中
    codex_bin = shutil.which("codex")
    if not codex_bin:
        logger.warning("login_codex_cli: codex CLI 未安装或不在 PATH 中，跳过")
        return None

    # 为每个 account_id 创建独立临时目录
    codex_home = CODEX_HOME_BASE / account_id
    codex_home.mkdir(parents=True, exist_ok=True)
    auth_json_path = codex_home / "auth.json"

    # 确保是干净的目录（删除可能残留的旧 auth.json）
    if auth_json_path.exists():
        auth_json_path.unlink()

    try:
        # 设置 CODEX_HOME 环境变量（仅对子进程生效）
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home.resolve())

        logger.info(
            "login_codex_cli: 开始 codex login (CODEX_HOME=%s) for account %s",
            codex_home, account_id,
        )

        result = subprocess.run(
            [codex_bin, "login", "--with-access-token"],
            input=access_token,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "unknown error"
            logger.warning(
                "login_codex_cli: codex login 失败 (rc=%d): %s",
                result.returncode, detail,
            )
            return None

        # 检查 auth.json 是否生成
        if not auth_json_path.exists():
            logger.warning(
                "login_codex_cli: codex login 命令成功但 auth.json 未生成于 %s",
                auth_json_path,
            )
            return None

        # 读取 auth.json 内容
        with open(auth_json_path, "r", encoding="utf-8") as f:
            auth_data = json.load(f)

        logger.info(
            "login_codex_cli: 成功获取 auth.json for account %s (keys: %s)",
            account_id, list(auth_data.keys()) if isinstance(auth_data, dict) else "?",
        )
        return auth_data

    except subprocess.TimeoutExpired:
        logger.warning("login_codex_cli: codex login 超时（30s）")
        return None
    except FileNotFoundError:
        logger.warning("login_codex_cli: 找不到 codex 可执行文件")
        return None
    except json.JSONDecodeError as exc:
        logger.warning("login_codex_cli: auth.json 解析失败: %s", exc)
        return None
    except Exception as exc:
        logger.warning("login_codex_cli: 未预期的异常: %s", exc)
        return None
    finally:
        # 清理临时 CODEX_HOME 目录，释放磁盘空间
        try:
            if codex_home.exists():
                shutil.rmtree(codex_home, ignore_errors=True)
        except Exception:
            pass
