"""Clash Proxy Manager — 通过 Clash REST API 管理代理节点。

**不影响系统代理**：代理 URL 仅作为参数传给各个 HTTP 请求（curl_cffi / requests / Playwright），
不会修改系统环境变量（HTTP_PROXY）或 Clash 系统代理开关。本机其他应用的网络不受影响。

默认配置（与 Clash Verge 外部控制一致）:
    API URL:  http://127.0.0.1:9097
    Secret:   123456
    Proxy:    http://127.0.0.1:7890 (Clash mixed port)

均衡策略:
    global       — 使用 Clash 当前全局节点，不切换
    round_robin  — 轮询组内所有节点
    lowest_delay — 每次选延迟最低的节点
    failover     — 连续失败 N 次后切换到下一个
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://127.0.0.1:9097"
DEFAULT_SECRET = "123456"
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 7897
DEFAULT_STRATEGY = "global"
DEFAULT_MAX_FAILS = 3
DEFAULT_GROUP = "GLOBAL"
DELAY_TEST_URL = "https://www.gstatic.com/generate_204"
DELAY_TIMEOUT_MS = 3000


class ClashProxyManager:
    """Clash 代理管理器（模块级单例）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._rr_index: dict[str, int] = {}        # round_robin 计数器 per group
        self._fail_count: dict[str, int] = {}       # failover 计数 per node
        self._fail_index: dict[str, int] = {}       # failover 位置 per group
        self._last_node: dict[str, str] = {}        # 上次使用的节点 per group

    # ── config helpers ──────────────────────────────────────────────

    @property
    def api_url(self) -> str:
        return self._config("clash_api_url", DEFAULT_API_URL)

    @property
    def secret(self) -> str:
        return self._config("clash_secret", DEFAULT_SECRET)

    @property
    def proxy_host(self) -> str:
        return self._config("clash_proxy_host", DEFAULT_PROXY_HOST)

    @property
    def proxy_port(self) -> int:
        return int(self._config("clash_proxy_port", DEFAULT_PROXY_PORT))

    @property
    def strategy(self) -> str:
        return self._config("clash_strategy", DEFAULT_STRATEGY)

    @property
    def max_fails(self) -> int:
        return int(self._config("clash_max_fails", DEFAULT_MAX_FAILS))

    @property
    def group(self) -> str:
        return self._config("clash_group", DEFAULT_GROUP)

    def _config(self, key: str, default: Any) -> Any:
        try:
            from core.config_store import config_store
            val = config_store.get(key, "")
            return val if val else str(default)
        except Exception:
            return default

    # ── HTTP helpers ─────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}"}

    def _request(self, method: str, path: str, timeout: int = 10, **kwargs) -> requests.Response | None:
        url = f"{self.api_url}{path}"
        try:
            resp = requests.request(method, url, headers=self._headers(), timeout=timeout, **kwargs)
            return resp
        except requests.RequestException as exc:
            logger.warning(f"[Clash] 请求失败 {method} {path}: {exc}")
            return None

    # ── public API ───────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        """检测是否可连接 Clash API。返回 (connected, version)。"""
        resp = self._request("GET", "/configs")
        if resp is None or resp.status_code != 200:
            return False, ""
        try:
            data = resp.json()
            return True, data.get("mode", "unknown")
        except Exception:
            return True, "unknown"

    def check_proxy_port(self) -> bool:
        """检测 Clash 代理端口是否在监听（TCP 连接测试）。"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.proxy_host, self.proxy_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def get_proxy_url(self) -> str:
        """返回 Clash 本地代理 URL（HTTP 代理）。"""
        return f"http://{self.proxy_host}:{self.proxy_port}"

    def get_status(self) -> dict:
        """获取 Clash 连接状态摘要。"""
        connected, mode = self.test_connection()
        proxy_ok = self.check_proxy_port() if connected else False
        nodes = self._fetch_nodes()
        current = self._current_node_from_raw(nodes)
        return {
            "connected": connected,
            "proxy_ok": proxy_ok,
            "mode": mode,
            "current_node": current,
            "proxy_url": self.get_proxy_url(),
            "node_count": len(nodes),
            "group": self.group,
            "strategy": self.strategy,
        }

    def get_nodes(self, group: str | None = None) -> list[dict]:
        """获取节点列表（含延迟信息）。"""
        group = group or self.group
        raw = self._fetch_nodes()
        return raw

    def switch_node(self, group: str, node_name: str) -> bool:
        """切换到指定组的某个节点。"""
        resp = self._request("PUT", f"/proxies/{group}", json={"name": node_name})
        if resp is not None and resp.status_code in (200, 204):
            self._last_node[group] = node_name
            self._fail_count[node_name] = 0
            return True
        return False

    def get_delay(self, node_name: str) -> int:
        """获取单个节点的延迟（毫秒）。超时返回 -1。"""
        url = f"/proxies/{node_name}/delay"
        params = {"url": DELAY_TEST_URL, "timeout": DELAY_TIMEOUT_MS}
        resp = self._request("GET", url, params=params)
        if resp is not None and resp.status_code == 200:
            try:
                return int(resp.json().get("delay", -1))
            except Exception:
                return -1
        return -1

    def get_group_delays(self, group: str | None = None) -> dict[str, int]:
        """一次请求获取分组内所有节点的延迟（毫秒）。

        使用 /group/{group}/delay API，一次调用返回组内全部节点延迟。
        返回 {node_name: delay_ms}，超时节点值为 -1。
        """
        group = group or self.group
        url = f"/group/{group}/delay"
        params = {"url": DELAY_TEST_URL, "timeout": DELAY_TIMEOUT_MS}
        resp = self._request("GET", url, params=params, timeout=15)
        if resp is None or resp.status_code != 200:
            return {}
        try:
            data = resp.json()
            if isinstance(data, dict):
                return {k: int(v) if v not in (None, -1) else -1 for k, v in data.items()}
            return {}
        except Exception as exc:
            logger.warning(f"[Clash] 解析分组延迟失败: {exc}")
            return {}

    # ── strategy selection ──────────────────────────────────────────

    def select_node(self) -> str | None:
        """根据策略选择节点并切换。返回选中的节点名，或 None（无需切换）。

        策略为 global 时始终返回 None（表示使用 Clash 自身选中的全局节点）。
        """
        strat = self.strategy
        group = self.group

        if strat == "global":
            return None

        nodes = self._fetch_nodes()
        if not nodes:
            return None

        with self._lock:
            if strat == "round_robin":
                return self._select_round_robin(group, nodes)
            elif strat == "lowest_delay":
                return self._select_lowest_delay(group, nodes)
            elif strat == "failover":
                return self._select_failover(group, nodes)
            else:
                return None

    def report_result(self, node_name: str, success: bool) -> None:
        """记录节点使用结果（failover 策略用）。"""
        with self._lock:
            if success:
                self._fail_count[node_name] = 0
            else:
                self._fail_count[node_name] = self._fail_count.get(node_name, 0) + 1

    # ── internal helpers ────────────────────────────────────────────

    def _fetch_nodes(self) -> list[dict]:
        """从 Clash API 拉取节点列表。"""
        resp = self._request("GET", "/proxies")
        if resp is None or resp.status_code != 200:
            return []
        try:
            data = resp.json()
            group_data = data.get("proxies", {}).get(self.group)
            if not group_data:
                return []
            all_nodes = group_data.get("all", [])
            # Clash returns node names in 'all' as strings
            if all_nodes and isinstance(all_nodes[0], str):
                return [{"name": n, "type": "unknown", "group": self.group} for n in all_nodes]
            return [
                {"name": n.get("name", n) if isinstance(n, dict) else str(n),
                 "type": n.get("type", "unknown") if isinstance(n, dict) else "unknown",
                 "group": self.group}
                for n in all_nodes
            ]
        except Exception as exc:
            logger.warning(f"[Clash] 解析节点列表失败: {exc}")
            return []

    def _current_node_from_raw(self, nodes: list[dict]) -> str:
        """从节点列表中获取 'now' 标记的当前节点。"""
        resp = self._request("GET", "/proxies")
        if resp is None or resp.status_code != 200:
            return ""
        try:
            data = resp.json()
            group_data = data.get("proxies", {}).get(self.group)
            if group_data:
                return group_data.get("now", "")
        except Exception:
            pass
        return ""

    # ── strategy implementations ────────────────────────────────────

    def _select_round_robin(self, group: str, nodes: list[dict]) -> str | None:
        if not nodes:
            return None
        idx = self._rr_index.get(group, -1) + 1
        if idx >= len(nodes):
            idx = 0
        self._rr_index[group] = idx
        node_name = nodes[idx]["name"]
        self.switch_node(group, node_name)
        return node_name

    def _select_lowest_delay(self, group: str, nodes: list[dict]) -> str | None:
        if not nodes:
            return None
        delays = self.get_group_delays(group)
        best_node: str | None = None
        best_delay: int = 99999
        for node in nodes:
            delay = delays.get(node["name"], -1)
            if 0 < delay < best_delay:
                best_delay = delay
                best_node = node["name"]
        if best_node:
            self.switch_node(group, best_node)
        return best_node

    def _select_failover(self, group: str, nodes: list[dict]) -> str | None:
        if not nodes:
            return None
        # 从上次位置开始找一个未超阈值的节点
        start = self._fail_index.get(group, 0) % len(nodes)
        for offset in range(len(nodes)):
            idx = (start + offset) % len(nodes)
            node_name = nodes[idx]["name"]
            if self._fail_count.get(node_name, 0) < self.max_fails:
                self.switch_node(group, node_name)
                self._fail_index[group] = idx
                return node_name
        # 所有节点都超阈值，重置计数器用第一个
        for node in nodes:
            self._fail_count[node["name"]] = 0
        node_name = nodes[0]["name"]
        self.switch_node(group, node_name)
        self._fail_index[group] = 0
        return node_name


# 模块级单例
clash_proxy = ClashProxyManager()
