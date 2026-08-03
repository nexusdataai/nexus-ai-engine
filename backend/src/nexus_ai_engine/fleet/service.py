"""Fleet aggregation from executions repo, admission, and worker locks."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from nexus_ai_engine.config import get_config
from nexus_ai_engine.contracts.execution_state import ExecutionStatus, NodeStatus
from nexus_ai_engine.execution.runtime_service import ExecutionRuntimeService

_ACTIVE = frozenset(
    {
        ExecutionStatus.RUNNING,
        ExecutionStatus.VERIFYING,
        ExecutionStatus.AWAITING_APPROVAL,
        ExecutionStatus.PAUSED,
    }
)


def _parse_window_hours(raw: str | None) -> int:
    if not raw:
        return 24
    value = raw.strip().lower().rstrip("h")
    try:
        hours = int(value)
    except ValueError:
        return 24
    return max(1, min(hours, 168))


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return round(ordered[idx], 2)


@dataclass
class FleetMonitorService:
    runtime: ExecutionRuntimeService
    _hostname: str = field(default_factory=lambda: os.getenv("HOSTNAME", "local-api"))

    async def _list_states(self, *, limit: int = 500) -> list[Any]:
        return await self.runtime.list_executions("", limit=limit)

    async def summary(self) -> dict[str, Any]:
        states = await self._list_states()
        active = sum(1 for s in states if s.status in _ACTIVE)
        queued = sum(1 for s in states if s.status is ExecutionStatus.PENDING)
        failed = sum(1 for s in states if s.status is ExecutionStatus.FAILED)

        config = get_config()
        global_limit = config.max_concurrent_jobs
        running_counter: int | None = None
        repo = self.runtime.repository
        if repo is not None and hasattr(repo, "get_running_count"):
            running_counter = await repo.get_running_count()

        workers = await self.workers()
        return {
            "active": active,
            "queued": queued,
            "failed": failed,
            "workers": len(workers.get("workers", [])),
            "global_limit": global_limit,
            "running_counter": running_counter,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def workers(self) -> dict[str, Any]:
        now = int(time.time())
        rows: list[dict[str, Any]] = [
            {
                "worker_id": self._hostname,
                "role": "api",
                "status": "healthy",
                "active_tasks": len(self.runtime._background),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        ]

        repo = self.runtime.repository
        if repo is not None and hasattr(repo, "list_active_locks"):
            for lock in await repo.list_active_locks(limit=200):
                ttl = int(lock.get("ttl") or 0)
                alive = ttl > now
                rows.append(
                    {
                        "worker_id": lock.get("worker_id", "unknown"),
                        "role": "executor",
                        "status": "healthy" if alive else "stale",
                        "execution_id": lock.get("execution_id"),
                        "lock_expires_at": datetime.fromtimestamp(ttl, tz=timezone.utc).isoformat()
                        if ttl
                        else None,
                        "last_seen": datetime.now(timezone.utc).isoformat(),
                    }
                )

        return {"workers": rows, "generated_at": datetime.now(timezone.utc).isoformat()}

    async def metrics(self, *, window: str | None = "24h") -> dict[str, Any]:
        hours = _parse_window_hours(window)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        states = await self._list_states(limit=1000)

        submitted = succeeded = failed = 0
        latencies_ms: list[float] = []
        hourly: dict[str, dict[str, int]] = {}

        for state in states:
            started = state.started_at
            finished = state.finished_at
            if started and started >= cutoff:
                submitted += 1
            if state.status is ExecutionStatus.SUCCEEDED and finished and finished >= cutoff:
                succeeded += 1
                bucket = finished.replace(minute=0, second=0, microsecond=0).isoformat()
                hourly.setdefault(bucket, {"succeeded": 0, "failed": 0})["succeeded"] += 1
            if state.status is ExecutionStatus.FAILED and finished and finished >= cutoff:
                failed += 1
                bucket = finished.replace(minute=0, second=0, microsecond=0).isoformat()
                hourly.setdefault(bucket, {"succeeded": 0, "failed": 0})["failed"] += 1

            if finished and finished >= cutoff:
                for node in state.nodes.values():
                    if (
                        node.status is NodeStatus.SUCCEEDED
                        and node.started_at
                        and node.finished_at
                        and node.finished_at >= cutoff
                    ):
                        delta = (node.finished_at - node.started_at).total_seconds() * 1000.0
                        if delta >= 0:
                            latencies_ms.append(delta)

        timeline = [
            {"hour": hour, **counts}
            for hour, counts in sorted(hourly.items())
        ]

        return {
            "window_hours": hours,
            "throughput": {
                "submitted": submitted,
                "succeeded": succeeded,
                "failed": failed,
            },
            "tool_dispatch_p95_ms": _percentile(latencies_ms, 95),
            "timeline": timeline,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
