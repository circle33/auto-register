"""Clash Proxy API — 代理管理与节点切换。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.clash_proxy import clash_proxy

router = APIRouter(prefix="/clash", tags=["clash"])


class ClashConfigRequest(BaseModel):
    clash_api_url: str = ""
    clash_secret: str = ""
    clash_proxy_host: str = ""
    clash_proxy_port: int = 0
    clash_strategy: str = ""
    clash_max_fails: int = 0
    clash_group: str = ""


class SwitchNodeRequest(BaseModel):
    group: str = "GLOBAL"
    node: str


@router.get("/status")
def clash_status():
    """Clash 连接状态 + 当前节点 + 代理 URL。"""
    try:
        return clash_proxy.get_status()
    except Exception as exc:
        raise HTTPException(500, f"获取 Clash 状态失败: {exc}")


@router.get("/nodes")
def clash_nodes(group: str = "", test_delay: bool = False):
    """获取节点列表。test_delay=true 时一次批量测试延迟（/group/{group}/delay）。"""
    try:
        nodes = clash_proxy.get_nodes(group or None)
        result = [{"name": n["name"], "type": n.get("type", "unknown"), "group": n.get("group", clash_proxy.group), "delay": 0} for n in nodes]

        if test_delay and result:
            delays = clash_proxy.get_group_delays(group or None)
            for item in result:
                item["delay"] = delays.get(item["name"], -1)

        # 按延迟升序，超时(-1)排到最后
        result.sort(key=lambda n: n["delay"] if n["delay"] > 0 else 99999)
        return result
    except Exception as exc:
        raise HTTPException(500, f"获取节点列表失败: {exc}")


@router.get("/config")
def clash_get_config():
    """读取 Clash 代理配置。"""
    try:
        from core.config_store import config_store
        from core.clash_proxy import (
            DEFAULT_API_URL, DEFAULT_SECRET, DEFAULT_PROXY_HOST,
            DEFAULT_PROXY_PORT, DEFAULT_STRATEGY, DEFAULT_MAX_FAILS, DEFAULT_GROUP,
        )
        return {
            "clash_api_url": config_store.get("clash_api_url", DEFAULT_API_URL),
            "clash_secret": config_store.get("clash_secret", DEFAULT_SECRET),
            "clash_proxy_host": config_store.get("clash_proxy_host", DEFAULT_PROXY_HOST),
            "clash_proxy_port": config_store.get("clash_proxy_port", str(DEFAULT_PROXY_PORT)),
            "clash_strategy": config_store.get("clash_strategy", DEFAULT_STRATEGY),
            "clash_max_fails": config_store.get("clash_max_fails", str(DEFAULT_MAX_FAILS)),
            "clash_group": config_store.get("clash_group", DEFAULT_GROUP),
        }
    except Exception as exc:
        raise HTTPException(500, f"读取配置失败: {exc}")


@router.put("/config")
def clash_config(body: ClashConfigRequest):
    """保存 Clash 代理配置。"""
    try:
        from core.config_store import config_store

        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            if value not in (None, ""):
                config_store.set(key, str(value))
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(500, f"保存配置失败: {exc}")


@router.post("/switch")
def clash_switch(body: SwitchNodeRequest):
    """切换节点。"""
    ok = clash_proxy.switch_node(body.group, body.node)
    if not ok:
        raise HTTPException(400, f"切换到节点 '{body.node}' 失败，请确认节点名和分组正确")
    return {"ok": True, "current_node": body.node}


@router.post("/test")
def clash_test():
    """测试 Clash API 连接。"""
    connected, mode = clash_proxy.test_connection()
    return {"connected": connected, "mode": mode}
