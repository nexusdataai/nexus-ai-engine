"""K3s / cluster resource usage snapshots for Infra → Resource Monitoring."""

from __future__ import annotations

import ast
import json
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional, Tuple

from loguru import logger

REDIS_KEY = "ai-engine:resource-snapshots"
MEMORY_LIMIT = 900
WINDOWS: Dict[str, Tuple[int, str]] = {
    "1h": (1, "minute"),
    "24h": (24, "hour"),
    "7d": (168, "hour"),
}

_memory: Deque[Dict[str, Any]] = deque(maxlen=MEMORY_LIMIT)
_lock = Lock()


def parse_k8s_cpu(raw: Any) -> Optional[float]:
    """Return cores from a Kubernetes quantity (n/u/m or cores)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.endswith("n"):
            return float(text[:-1]) / 1_000_000_000.0
        if text.endswith("u"):
            return float(text[:-1]) / 1_000_000.0
        if text.endswith("m"):
            return float(text[:-1]) / 1000.0
        return float(text)
    except ValueError:
        return None


def parse_k8s_bytes(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    multipliers = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
    }
    try:
        for suffix, mult in multipliers.items():
            if text.endswith(suffix):
                return float(text[: -len(suffix)]) * mult
        return float(text)
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pct(used: Optional[float], total: Optional[float]) -> Optional[float]:
    if used is None or not total:
        return None
    return round(max(0.0, min(100.0, 100.0 * used / total)), 1)


def parse_kubelet_summary(raw: Any) -> Optional[Dict[str, Any]]:
    """The python client often returns a Python-repr string, not JSON."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    try:
        data = ast.literal_eval(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def network_bytes(net: Optional[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int]]:
    if not net:
        return None, None
    if net.get("rxBytes") is not None:
        return int(net["rxBytes"]), int(net.get("txBytes") or 0)
    interfaces = net.get("interfaces") or []
    chosen = None
    name = net.get("name")
    if name:
        chosen = next((item for item in interfaces if item.get("name") == name), None)
    if chosen is None:
        chosen = next((item for item in interfaces if item.get("name") not in ("lo", "lo0")), None)
    if chosen is None and interfaces:
        chosen = interfaces[0]
    if not chosen or chosen.get("rxBytes") is None:
        return None, None
    return int(chosen["rxBytes"]), int(chosen.get("txBytes") or 0)


class ResourceMonitoringService:
    def __init__(self) -> None:
        self._k8s = None

    def _k8s_clients(self):
        if self._k8s is not None:
            return self._k8s
        try:
            from kubernetes import client, config

            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()
            self._k8s = (client.CoreV1Api(), client.CustomObjectsApi())
            return self._k8s
        except Exception as exc:
            logger.debug("Resource monitoring k8s client unavailable: {}", exc)
            return None, None

    def collect_snapshot(self) -> Dict[str, Any]:
        point = {
            "timestamp": _now().isoformat(),
            "cpu_pct": None,
            "memory_pct": None,
            "storage_pct": None,
            "network_rx_mbps": None,
            "network_tx_mbps": None,
            "rx_bytes": None,
            "tx_bytes": None,
            "jobs_running": self._jobs_running(),
            "node": None,
        }
        core, custom = self._k8s_clients()
        self._fill_from_metrics(custom, core, point)
        self._fill_from_kubelet(core, point)
        self._fill_network_rate(point)
        self._write(point)
        return point

    def _jobs_running(self) -> int:
        try:
            from .job_queue_service import get_queue_snapshot

            snap = get_queue_snapshot()
            return int(snap.get("active") or 0)
        except Exception:
            return 0

    def _fill_from_metrics(self, custom, core, point: Dict[str, Any]) -> None:
        if custom is None:
            return
        try:
            metrics = custom.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
            )
        except Exception as exc:
            logger.debug("Node metrics unavailable: {}", exc)
            return
        items = metrics.get("items") or []
        if not items:
            return
        cpu_used = 0.0
        mem_used = 0.0
        cpu_cap = 0.0
        mem_cap = 0.0
        names: List[str] = []
        for item in items:
            name = (item.get("metadata") or {}).get("name")
            usage = item.get("usage") or {}
            cpu = parse_k8s_cpu(usage.get("cpu"))
            mem = parse_k8s_bytes(usage.get("memory"))
            if cpu is not None:
                cpu_used += cpu
            if mem is not None:
                mem_used += mem
            if name:
                names.append(name)
        if core is not None:
            try:
                nodes = core.list_node()
                for node in nodes.items or []:
                    cap = (node.status.capacity or {}) if node.status else {}
                    cpu = parse_k8s_cpu(cap.get("cpu"))
                    mem = parse_k8s_bytes(cap.get("memory"))
                    if cpu is not None:
                        cpu_cap += cpu
                    if mem is not None:
                        mem_cap += mem
            except Exception as exc:
                logger.debug("Node capacity unavailable: {}", exc)
        point["cpu_pct"] = _pct(cpu_used, cpu_cap)
        point["memory_pct"] = _pct(mem_used, mem_cap)
        point["node"] = names[0] if names else None

    def _fill_from_kubelet(self, core, point: Dict[str, Any]) -> None:
        if core is None:
            return
        name = point.get("node")
        if not name:
            try:
                nodes = core.list_node()
                if nodes.items:
                    name = nodes.items[0].metadata.name
                    point["node"] = name
            except Exception:
                return
        if not name:
            return
        try:
            raw = core.connect_get_node_proxy_with_path(name=name, path="stats/summary")
        except Exception as exc:
            logger.debug("Kubelet stats unavailable: {}", exc)
            return
        data = parse_kubelet_summary(raw)
        if not data:
            return
        node = data.get("node") or {}
        fs = node.get("fs") or {}
        used = fs.get("usedBytes")
        cap = fs.get("capacityBytes")
        if used is not None and cap:
            point["storage_pct"] = _pct(float(used), float(cap))
        rx, tx = network_bytes(node.get("network") or {})
        if rx is not None:
            point["rx_bytes"] = rx
        if tx is not None:
            point["tx_bytes"] = tx

    def _fill_network_rate(self, point: Dict[str, Any]) -> None:
        prev = self._latest()
        if not prev or point.get("rx_bytes") is None or prev.get("rx_bytes") is None:
            return
        prev_ts = prev.get("timestamp")
        try:
            prev_dt = datetime.fromisoformat(str(prev_ts).replace("Z", "+00:00"))
            if prev_dt.tzinfo is None:
                prev_dt = prev_dt.replace(tzinfo=timezone.utc)
            elapsed = max(1.0, (_now() - prev_dt).total_seconds())
        except Exception:
            return
        rx_delta = max(0, int(point["rx_bytes"]) - int(prev["rx_bytes"]))
        tx_delta = max(0, int(point.get("tx_bytes") or 0) - int(prev.get("tx_bytes") or 0))
        point["network_rx_mbps"] = round((rx_delta * 8) / elapsed / 1_000_000, 3)
        point["network_tx_mbps"] = round((tx_delta * 8) / elapsed / 1_000_000, 3)

    def _latest(self) -> Optional[Dict[str, Any]]:
        with _lock:
            if _memory:
                return dict(_memory[-1])
        return None

    def _write(self, point: Dict[str, Any]) -> None:
        stored = {
            k: point.get(k)
            for k in (
                "timestamp",
                "cpu_pct",
                "memory_pct",
                "storage_pct",
                "network_rx_mbps",
                "network_tx_mbps",
                "rx_bytes",
                "tx_bytes",
                "jobs_running",
                "node",
            )
        }
        with _lock:
            _memory.append(stored)
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if redis_available() and redis_sync is not None:
                client = redis_sync.from_url(REDIS_URL, decode_responses=True)
                client.lpush(REDIS_KEY, json.dumps(stored))
                client.ltrim(REDIS_KEY, 0, MEMORY_LIMIT - 1)
        except Exception as exc:
            logger.debug("Resource snapshot Redis write skipped: {}", exc)

    def _history(self, hours: float) -> List[Dict[str, Any]]:
        cutoff = (_now() - timedelta(hours=hours)).isoformat()
        points: List[Dict[str, Any]] = []
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if redis_available() and redis_sync is not None:
                client = redis_sync.from_url(REDIS_URL, decode_responses=True)
                for raw in client.lrange(REDIS_KEY, 0, MEMORY_LIMIT):
                    item = json.loads(raw)
                    if (item.get("timestamp") or "") >= cutoff:
                        points.append(item)
        except Exception:
            pass
        if not points:
            with _lock:
                points = [dict(p) for p in _memory if (p.get("timestamp") or "") >= cutoff]
        points.sort(key=lambda p: p.get("timestamp") or "")
        return points

    def get_summary(self, window: str = "1h") -> Dict[str, Any]:
        hours, grain = WINDOWS.get(window, WINDOWS["1h"])
        current = self.collect_snapshot()
        history = self._history(hours)
        if not history:
            history = [current]
        net = None
        if current.get("network_rx_mbps") is not None or current.get("network_tx_mbps") is not None:
            net = round((current.get("network_rx_mbps") or 0) + (current.get("network_tx_mbps") or 0), 3)
        return {
            "window": window,
            "grain": grain,
            "timestamp": current.get("timestamp"),
            "node": current.get("node"),
            "kpis": [
                {"id": "cpu", "label": "CPU", "value": current.get("cpu_pct"), "unit": "%"},
                {"id": "memory", "label": "Memory", "value": current.get("memory_pct"), "unit": "%"},
                {"id": "storage", "label": "Storage", "value": current.get("storage_pct"), "unit": "%"},
                {"id": "network", "label": "Network", "value": net, "unit": "Mbps"},
                {"id": "jobs", "label": "Jobs running", "value": current.get("jobs_running"), "unit": "count"},
            ],
            "points": [
                {
                    "timestamp": p.get("timestamp"),
                    "cpu_pct": p.get("cpu_pct"),
                    "memory_pct": p.get("memory_pct"),
                    "storage_pct": p.get("storage_pct"),
                    "network_rx_mbps": p.get("network_rx_mbps"),
                    "network_tx_mbps": p.get("network_tx_mbps"),
                    "jobs_running": p.get("jobs_running") or 0,
                }
                for p in history
            ],
        }


_service: Optional[ResourceMonitoringService] = None


def get_resource_monitoring_service() -> ResourceMonitoringService:
    global _service
    if _service is None:
        _service = ResourceMonitoringService()
    return _service


def record_resource_snapshot() -> Dict[str, Any]:
    return get_resource_monitoring_service().collect_snapshot()
