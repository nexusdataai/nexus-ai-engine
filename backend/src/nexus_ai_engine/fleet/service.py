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


def _parse_job_time(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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
        dsl_active = sum(1 for s in states if s.status in _ACTIVE)
        dsl_queued = sum(1 for s in states if s.status is ExecutionStatus.PENDING)
        failed = sum(1 for s in states if s.status is ExecutionStatus.FAILED)

        stage_active = 0
        stage_queued = 0
        try:
            from nexus_ai_engine.services.job_queue_service import (
                get_active_job_count,
                get_stage_jobs_queued,
                is_queue_mode,
                redis_available,
            )

            if is_queue_mode() and redis_available():
                stage_active = get_active_job_count()
                stage_queued = get_stage_jobs_queued()
        except Exception:
            pass

        config = get_config()
        global_limit = config.max_concurrent_jobs
        running_counter: int | None = None
        repo = self.runtime.repository
        if repo is not None and hasattr(repo, "get_running_count"):
            running_counter = await repo.get_running_count()

        workers = await self.workers()
        return {
            "active": dsl_active + stage_active,
            "queued": dsl_queued + stage_queued,
            "failed": failed,
            "workers": len(workers.get("workers", [])),
            "global_limit": global_limit,
            "running_counter": running_counter,
            "dsl_executions_active": dsl_active,
            "dsl_executions_queued": dsl_queued,
            "stage_jobs_active": stage_active,
            "stage_jobs_queued": stage_queued,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _queue_job_workers(self) -> list[dict[str, Any]] | None:
        """Job-worker consumers/pods when running in Redis queue mode.

        Returns None in inline mode so the API hostname + DSL locks remain
        the worker list. Returns [] (not None) in queue mode with no workers
        so the dashboard does not fall back to counting the API pod.
        """
        try:
            from nexus_ai_engine.services.job_queue_service import is_queue_mode

            if not is_queue_mode():
                return None
            from nexus_ai_engine.services.worker_management_service import (
                get_worker_management_service,
            )

            payload = get_worker_management_service().list_workers()
        except Exception:
            return None

        rows: list[dict[str, Any]] = []
        for worker in payload.get("workers") or []:
            current = worker.get("current_job") or {}
            rows.append(
                {
                    "worker_id": worker.get("worker_id") or worker.get("consumer_name") or "unknown",
                    "role": "job-worker",
                    "status": worker.get("status") or "offline",
                    "active_tasks": 1 if current.get("job_id") else 0,
                    "execution_id": current.get("job_id"),
                    "last_seen": worker.get("last_seen")
                    or datetime.now(timezone.utc).isoformat(),
                }
            )
        return rows

    async def workers(self) -> dict[str, Any]:
        queue_rows = self._queue_job_workers()
        if queue_rows is not None:
            return {
                "workers": queue_rows,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

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

    def _stage_job_throughput(self, cutoff: datetime) -> tuple[int, int, int]:
        """Count transformation/stage jobs in the window (not just DSL executions)."""
        from nexus_ai_engine.adapters.dynamodb.journey_manager import (
            ComprehensiveJourneyManager,
        )

        manager = ComprehensiveJourneyManager()
        submitted = succeeded = failed = 0
        for journey in manager.list_journeys() or []:
            journey_id = journey.get("journeyId") or journey.get("journey_id")
            if not journey_id:
                continue
            for job in manager.list_jobs(str(journey_id), limit=200):
                started = _parse_job_time(job.get("startTime") or job.get("started_at"))
                finished = _parse_job_time(job.get("endTime") or job.get("finished_at"))
                status = str(job.get("status") or "").lower()
                if started and started >= cutoff:
                    submitted += 1
                stamp = finished or started
                if stamp is None or stamp < cutoff:
                    continue
                if status in ("completed", "succeeded", "success"):
                    succeeded += 1
                elif status in ("failed", "error"):
                    failed += 1
        return submitted, succeeded, failed

    async def metrics(self, *, window: str | None = "24h") -> dict[str, Any]:
        hours = _parse_window_hours(window)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        states = await self._list_states(limit=1000)

        submitted = succeeded = failed = 0
        latencies_ms: list[float] = []
        hourly: dict[str, dict[str, int]] = {}

        try:
            stage_submitted, stage_succeeded, stage_failed = self._stage_job_throughput(cutoff)
            submitted += stage_submitted
            succeeded += stage_succeeded
            failed += stage_failed
        except Exception:
            pass

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
