"""Redis Cache overview and safe flush for Operations → Infra."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

from .app_trends_service import QUEUE_SNAPSHOT_KEY
from .job_queue_service import (
    JOB_ACTIVE_COUNTER_KEY,
    JOB_CANCELLED_SET_KEY,
    JOB_CONSUMER_GROUP,
    JOB_STREAM_KEY,
    JOB_WAITING_SET_KEY,
    REDIS_URL,
    get_queue_snapshot,
    is_queue_mode,
    redis_available,
    redis_sync,
)
from .resource_monitoring_service import REDIS_KEY as RESOURCE_SNAPSHOT_KEY
from .sla_monitoring_service import REDIS_SNAPSHOT_KEY as SLA_SNAPSHOT_KEY

SNAPSHOT_KEYS = (SLA_SNAPSHOT_KEY, QUEUE_SNAPSHOT_KEY, RESOURCE_SNAPSHOT_KEY)
PROTECTED_PREFIXES = ("ai-engine:jobs",)
SSE_HISTORY_MATCH = "sse:*:history"


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or url
    port = parsed.port
    return f"{host}:{port}" if port else host


def _client():
    if not redis_available() or redis_sync is None:
        return None
    return redis_sync.from_url(REDIS_URL, decode_responses=True)


def _llen(client, key: str) -> int:
    try:
        return int(client.llen(key) or 0)
    except Exception:
        return 0


def _scan_keys(client, match: str, limit: int = 400) -> List[str]:
    found: List[str] = []
    try:
        for key in client.scan_iter(match=match, count=200):
            found.append(key)
            if len(found) >= limit:
                break
    except Exception as exc:
        logger.debug("Redis scan {} failed: {}", match, exc)
    return found


class RedisCacheService:
    def get_overview(self) -> Dict[str, Any]:
        ping_ms: Optional[float] = None
        connected = False
        ping_message = "redis unavailable"
        memory: Dict[str, Any] = {}
        client = None
        try:
            client = _client()
            if client is not None:
                start = datetime.now(timezone.utc)
                client.ping()
                ping_ms = round((datetime.now(timezone.utc) - start).total_seconds() * 1000, 2)
                connected = True
                ping_message = "ok"
                info = client.info("memory") or {}
                memory = {
                    "used_memory_human": info.get("used_memory_human"),
                    "maxmemory_human": info.get("maxmemory_human") or "0",
                    "used_memory": info.get("used_memory"),
                }
        except Exception as exc:
            ping_message = str(exc)
            client = None

        snapshots = [
            {"id": "sla", "key": SLA_SNAPSHOT_KEY, "label": "SLA snapshots", "length": _llen(client, SLA_SNAPSHOT_KEY) if client else 0},
            {"id": "queue", "key": QUEUE_SNAPSHOT_KEY, "label": "Queue snapshots", "length": _llen(client, QUEUE_SNAPSHOT_KEY) if client else 0},
            {"id": "resources", "key": RESOURCE_SNAPSHOT_KEY, "label": "Resource snapshots", "length": _llen(client, RESOURCE_SNAPSHOT_KEY) if client else 0},
        ]
        sse_keys = _scan_keys(client, SSE_HISTORY_MATCH) if client else []
        queue = {}
        try:
            queue = get_queue_snapshot() if connected else {}
        except Exception:
            queue = {}
        stream_len = 0
        cancelled = 0
        if client is not None:
            try:
                stream_len = int(client.xlen(JOB_STREAM_KEY) or 0)
            except Exception:
                stream_len = 0
            try:
                cancelled = int(client.scard(JOB_CANCELLED_SET_KEY) or 0)
            except Exception:
                cancelled = 0

        return {
            "connected": connected,
            "ping_ms": ping_ms,
            "ping_message": ping_message,
            "memory": memory,
            "effective_config": {
                "redis_host": _host_from_url(REDIS_URL),
                "job_stream_key": JOB_STREAM_KEY,
                "consumer_group": JOB_CONSUMER_GROUP,
                "queue_mode": is_queue_mode(),
                "sse_history_max": int(os.getenv("SSE_HISTORY_MAX", "100")),
            },
            "snapshots": {
                "keys": snapshots,
                "key_total": sum(item["length"] for item in snapshots),
            },
            "queue": {
                "stream_length": stream_len,
                "waiting": queue.get("lag") or 0,
                "active": queue.get("active") or 0,
                "pending": queue.get("pending") or 0,
                "consumers": queue.get("consumer_count") or 0,
                "cancelled": cancelled,
                "protected": True,
            },
            "sse": {
                "key_total": len(sse_keys),
                "keys": sse_keys[:25],
                "match": SSE_HISTORY_MATCH,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def collect_snapshots(self) -> Dict[str, Any]:
        from .sla_monitoring_service import get_sla_monitoring_service

        await get_sla_monitoring_service().collect_and_record(window_hours=1)
        return {"collected": True, "keys": list(SNAPSHOT_KEYS)}

    def flush_snapshots(self) -> Dict[str, Any]:
        client = _client()
        if client is None:
            return {"flushed": False, "keys_deleted": 0, "error": "Redis unavailable"}
        deleted = 0
        for key in SNAPSHOT_KEYS:
            try:
                deleted += int(client.delete(key) or 0)
            except Exception as exc:
                logger.warning("Snapshot flush failed for {}: {}", key, exc)
        logger.warning("Redis snapshot flush deleted={}", deleted)
        return {"flushed": True, "keys_deleted": deleted, "keys": list(SNAPSHOT_KEYS)}

    def flush_sse_history(self) -> Dict[str, Any]:
        client = _client()
        if client is None:
            return {"flushed": False, "keys_deleted": 0, "error": "Redis unavailable"}
        keys = _scan_keys(client, SSE_HISTORY_MATCH, limit=2000)
        deleted = 0
        for key in keys:
            if not str(key).endswith(":history"):
                continue
            if str(key).startswith(PROTECTED_PREFIXES):
                continue
            try:
                deleted += int(client.delete(key) or 0)
            except Exception as exc:
                logger.warning("SSE flush failed for {}: {}", key, exc)
        logger.warning("Redis SSE history flush deleted={}", deleted)
        return {"flushed": True, "keys_deleted": deleted}


_service: Optional[RedisCacheService] = None


def get_redis_cache_service() -> RedisCacheService:
    global _service
    if _service is None:
        _service = RedisCacheService()
    return _service
