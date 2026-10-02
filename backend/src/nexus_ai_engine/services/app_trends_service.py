"""App monitoring trends — executions, queue, and schedules."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional, Tuple

from loguru import logger

from .worker_management_service import two_wave_lag_count

APP_TABS = ("executions", "queue", "schedules")
WINDOWS: Dict[str, Tuple[int, str]] = {
    "24h": (24, "hour"),
    "7d": (168, "day"),
    "30d": (720, "day"),
}
QUEUE_SNAPSHOT_KEY = "ai-engine:queue-snapshots"
QUEUE_SNAPSHOT_LIMIT = 900

_queue_memory: Deque[Dict[str, Any]] = deque(maxlen=QUEUE_SNAPSHOT_LIMIT)
_queue_lock = Lock()


def parse_window(window: str) -> Tuple[int, str]:
    return WINDOWS.get(window, WINDOWS["24h"])


def _parse_time(raw: Any) -> Optional[datetime]:
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


def _bucket_start(dt: datetime, grain: str) -> datetime:
    if grain == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _iter_buckets(hours: int, grain: str) -> List[datetime]:
    now = datetime.now(timezone.utc)
    end = _bucket_start(now, grain)
    step = timedelta(hours=1) if grain == "hour" else timedelta(days=1)
    start = _bucket_start(now - timedelta(hours=hours), grain)
    buckets: List[datetime] = []
    cursor = start
    while cursor <= end:
        buckets.append(cursor)
        cursor += step
    return buckets


def _is_success(status: str) -> bool:
    return status in {"completed", "succeeded", "success"}


def _is_failure(status: str) -> bool:
    return status in {"failed", "error"}


def _is_scheduled(triggered_by: str) -> bool:
    return triggered_by in {"scheduler", "schedule", "cron"}


def record_queue_snapshot() -> Dict[str, Any]:
    try:
        from .job_queue_service import get_queue_snapshot

        snap = get_queue_snapshot()
    except Exception as exc:
        logger.debug("Queue snapshot skipped: {}", exc)
        return {}
    point = {
        "timestamp": snap.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "waiting": int(snap.get("lag") or 0),
        "running": int(snap.get("active") or 0),
        "pending": int(snap.get("pending") or 0),
        "queued": int(snap.get("queued") or 0),
        "capacity": int(snap.get("running_capacity") or 0),
        "max_global": int(snap.get("max_global") or 0),
    }
    with _queue_lock:
        _queue_memory.append(point)
    try:
        from .job_queue_service import REDIS_URL, redis_available, redis_sync

        if redis_available() and redis_sync is not None:
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            client.lpush(QUEUE_SNAPSHOT_KEY, json.dumps(point))
            client.ltrim(QUEUE_SNAPSHOT_KEY, 0, QUEUE_SNAPSHOT_LIMIT - 1)
    except Exception as exc:
        logger.debug("Queue snapshot Redis write skipped: {}", exc)
    return point


def _read_queue_history(hours: int) -> List[Dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    points: List[Dict[str, Any]] = []
    try:
        from .job_queue_service import REDIS_URL, redis_available, redis_sync

        if redis_available() and redis_sync is not None:
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            for raw in client.lrange(QUEUE_SNAPSHOT_KEY, 0, QUEUE_SNAPSHOT_LIMIT):
                item = json.loads(raw)
                if (item.get("timestamp") or "") >= cutoff:
                    points.append(item)
    except Exception:
        pass
    if not points:
        with _queue_lock:
            points = [p for p in _queue_memory if (p.get("timestamp") or "") >= cutoff]
    points.sort(key=lambda p: p.get("timestamp") or "")
    return points


class AppTrendsService:
    def __init__(self) -> None:
        self._engine: Any = None

    def bind_engine(self, engine: Any) -> None:
        self._engine = engine

    async def get_trends(self, tab: str, window: str = "24h") -> Dict[str, Any]:
        tab = tab.lower()
        if tab not in APP_TABS:
            return {"tab": tab, "error": f"Unknown tab: {tab}"}
        hours, grain = parse_window(window)
        if tab == "executions":
            return await self._executions(window, hours, grain)
        if tab == "queue":
            return self._queue(window, hours, grain)
        return self._schedules(window, hours, grain)

    def _list_stage_jobs(self) -> List[Dict[str, Any]]:
        try:
            from ..adapters.dynamodb.journey_manager import ComprehensiveJourneyManager

            manager = ComprehensiveJourneyManager()
            jobs: List[Dict[str, Any]] = []
            for journey in manager.list_journeys() or []:
                journey_id = journey.get("journeyId") or journey.get("journey_id")
                if not journey_id:
                    continue
                jobs.extend(manager.list_jobs(str(journey_id), limit=300) or [])
            return jobs
        except Exception as exc:
            logger.debug("Stage job listing failed: {}", exc)
            return []

    async def _dsl_events(self, cutoff: datetime) -> List[Dict[str, Any]]:
        runtime = getattr(self._engine, "execution_runtime", None)
        if runtime is None:
            return []
        try:
            from ..contracts.execution_state import ExecutionStatus
            from ..fleet.service import FleetMonitorService

            states = await FleetMonitorService(runtime=runtime)._list_states(limit=1000)
            events: List[Dict[str, Any]] = []
            for state in states:
                started = state.started_at
                finished = state.finished_at
                stamp = finished or started
                if stamp is None or stamp < cutoff:
                    continue
                status = "succeeded" if state.status is ExecutionStatus.SUCCEEDED else (
                    "failed" if state.status is ExecutionStatus.FAILED else str(state.status.value)
                )
                events.append({
                    "startTime": started.isoformat() if started else None,
                    "endTime": finished.isoformat() if finished else None,
                    "status": status,
                    "triggeredBy": "dsl",
                })
            return events
        except Exception as exc:
            logger.debug("DSL execution listing failed: {}", exc)
            return []

    async def _executions(self, window: str, hours: int, grain: str) -> Dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        jobs = self._list_stage_jobs()
        jobs.extend(await self._dsl_events(cutoff))
        buckets = {b.isoformat(): {"succeeded": 0, "failed": 0, "submitted": 0} for b in _iter_buckets(hours, grain)}
        submitted = succeeded = failed = 0
        for job in jobs:
            started = _parse_time(job.get("startTime") or job.get("started_at"))
            finished = _parse_time(job.get("endTime") or job.get("finished_at"))
            status = str(job.get("status") or "").lower()
            if started and started >= cutoff:
                submitted += 1
                key = _bucket_start(started, grain).isoformat()
                if key in buckets:
                    buckets[key]["submitted"] += 1
            stamp = finished or started
            if stamp is None or stamp < cutoff:
                continue
            key = _bucket_start(stamp, grain).isoformat()
            if key not in buckets:
                continue
            if _is_success(status):
                succeeded += 1
                buckets[key]["succeeded"] += 1
            elif _is_failure(status):
                failed += 1
                buckets[key]["failed"] += 1

        total_done = succeeded + failed
        success_rate = round(100.0 * succeeded / total_done, 1) if total_done else 100.0
        active = 0
        p95 = None
        try:
            from ..fleet.service import FleetMonitorService

            runtime = getattr(self._engine, "execution_runtime", None)
            if runtime is not None:
                summary = await FleetMonitorService(runtime=runtime).summary()
                active = int(summary.get("active") or 0)
                metrics = await FleetMonitorService(runtime=runtime).metrics(window=f"{hours}h")
                p95 = metrics.get("tool_dispatch_p95_ms")
        except Exception:
            pass

        points = []
        for key, counts in buckets.items():
            done = counts["succeeded"] + counts["failed"]
            points.append({
                "timestamp": key,
                "succeeded": counts["succeeded"],
                "failed": counts["failed"],
                "submitted": counts["submitted"],
                "rate": round(100.0 * counts["succeeded"] / done, 1) if done else None,
            })
        return {
            "tab": "executions",
            "window": window,
            "grain": grain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kpis": [
                {"id": "active", "label": "Active now", "value": active, "unit": "count"},
                {"id": "submitted", "label": "Submitted", "value": submitted, "unit": "count"},
                {"id": "succeeded", "label": "Succeeded", "value": succeeded, "unit": "count"},
                {"id": "failed", "label": "Failed", "value": failed, "unit": "count"},
                {"id": "success_rate", "label": "Success rate", "value": success_rate, "unit": "%"},
                {"id": "p95", "label": "Dispatch p95", "value": p95, "unit": "ms"},
            ],
            "series": [
                {"id": "succeeded", "label": "Succeeded", "color": "#22c55e", "axis": "count"},
                {"id": "failed", "label": "Failed", "color": "#ef4444", "axis": "count"},
                {"id": "rate", "label": "Success rate", "color": "#eab308", "axis": "percent"},
            ],
            "mix": [
                {"id": "succeeded", "label": "Succeeded", "value": succeeded, "color": "#22c55e"},
                {"id": "failed", "label": "Failed", "value": failed, "color": "#ef4444"},
            ],
            "points": points,
            "chart_title": "Execution volume and success rate",
        }

    def _queue(self, window: str, hours: int, grain: str) -> Dict[str, Any]:
        current = record_queue_snapshot()
        history = _read_queue_history(hours)
        if not history and current:
            history = [current]
        buckets = {
            b.isoformat(): {"waiting": [], "running": [], "pending": []}
            for b in _iter_buckets(hours, grain)
        }
        for item in history:
            ts = _parse_time(item.get("timestamp"))
            if ts is None:
                continue
            key = _bucket_start(ts, grain).isoformat()
            if key not in buckets:
                continue
            buckets[key]["waiting"].append(int(item.get("waiting") or 0))
            buckets[key]["running"].append(int(item.get("running") or 0))
            buckets[key]["pending"].append(int(item.get("pending") or 0))

        def _avg(values: List[int]) -> Optional[float]:
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        points = []
        for key, series in buckets.items():
            waiting = _avg(series["waiting"])
            running = _avg(series["running"])
            pending = _avg(series["pending"])
            horizon = None
            try:
                from .job_execution_config_service import get_job_execution_config

                horizon = two_wave_lag_count(get_job_execution_config().get_worker_threads())
            except Exception:
                horizon = None
            lag_pct = None
            if waiting is not None and horizon:
                lag_pct = round(100.0 * waiting / max(horizon, 1), 1)
            points.append({
                "timestamp": key,
                "waiting": waiting or 0,
                "running": running or 0,
                "pending": pending or 0,
                "rate": lag_pct,
            })

        waiting_now = int(current.get("waiting") or 0)
        running_now = int(current.get("running") or 0)
        pending_now = int(current.get("pending") or 0)
        capacity = int(current.get("capacity") or 0)
        max_global = int(current.get("max_global") or 0)
        try:
            from .job_execution_config_service import get_job_execution_config

            horizon = two_wave_lag_count(get_job_execution_config().get_worker_threads())
        except Exception:
            horizon = 0
        lag_pct = round(100.0 * waiting_now / max(horizon, 1), 1) if horizon else 0.0
        return {
            "tab": "queue",
            "window": window,
            "grain": grain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kpis": [
                {"id": "waiting", "label": "Waiting", "value": waiting_now, "unit": "count"},
                {"id": "running", "label": "Running", "value": running_now, "unit": "count"},
                {"id": "pending", "label": "Claimed / pending", "value": pending_now, "unit": "count"},
                {"id": "capacity", "label": "Running capacity", "value": capacity, "unit": "count"},
                {"id": "slots", "label": "Global slots", "value": max_global, "unit": "count"},
                {"id": "lag_pct", "label": "Lag vs 2-wave", "value": lag_pct, "unit": "%"},
            ],
            "series": [
                {"id": "waiting", "label": "Waiting", "color": "#8b5cf6", "axis": "count"},
                {"id": "running", "label": "Running", "color": "#3b82f6", "axis": "count"},
                {"id": "rate", "label": "Lag vs horizon", "color": "#eab308", "axis": "percent"},
            ],
            "mix": [
                {"id": "waiting", "label": "Waiting", "value": waiting_now, "color": "#8b5cf6"},
                {"id": "running", "label": "Running", "value": running_now, "color": "#3b82f6"},
                {"id": "pending", "label": "Pending", "value": pending_now, "color": "#64748b"},
            ],
            "points": points,
            "chart_title": "Queue depth and lag vs 2-wave horizon",
        }

    def _schedules(self, window: str, hours: int, grain: str) -> Dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        soon = datetime.now(timezone.utc) + timedelta(hours=1)
        schedules: List[Dict[str, Any]] = []
        try:
            from .scheduler_service import SchedulerService

            schedules = SchedulerService.get_instance().list_schedules() or []
        except Exception as exc:
            logger.debug("Schedule list failed: {}", exc)

        total = len(schedules)
        enabled = sum(1 for s in schedules if s.get("enabled"))
        due_soon = 0
        last_failed = 0
        for row in schedules:
            next_run = _parse_time(row.get("nextRunAt") or row.get("next_run_at"))
            if row.get("enabled") and next_run and next_run <= soon:
                due_soon += 1
            status = str(row.get("lastJobStatus") or row.get("last_job_status") or "").lower()
            if _is_failure(status):
                last_failed += 1

        jobs = self._list_stage_jobs()
        buckets = {b.isoformat(): {"succeeded": 0, "failed": 0} for b in _iter_buckets(hours, grain)}
        fired = succeeded = failed = 0
        for job in jobs:
            if not _is_scheduled(str(job.get("triggeredBy") or job.get("triggered_by") or "").lower()):
                continue
            started = _parse_time(job.get("startTime"))
            finished = _parse_time(job.get("endTime"))
            stamp = finished or started
            if stamp is None or stamp < cutoff:
                continue
            fired += 1
            status = str(job.get("status") or "").lower()
            key = _bucket_start(stamp, grain).isoformat()
            if key not in buckets:
                continue
            if _is_success(status):
                succeeded += 1
                buckets[key]["succeeded"] += 1
            elif _is_failure(status):
                failed += 1
                buckets[key]["failed"] += 1

        done = succeeded + failed
        success_rate = round(100.0 * succeeded / done, 1) if done else 100.0
        points = []
        for key, counts in buckets.items():
            bucket_done = counts["succeeded"] + counts["failed"]
            points.append({
                "timestamp": key,
                "succeeded": counts["succeeded"],
                "failed": counts["failed"],
                "rate": round(100.0 * counts["succeeded"] / bucket_done, 1) if bucket_done else None,
            })
        return {
            "tab": "schedules",
            "window": window,
            "grain": grain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kpis": [
                {"id": "total", "label": "Schedules", "value": total, "unit": "count"},
                {"id": "enabled", "label": "Enabled", "value": enabled, "unit": "count"},
                {"id": "due_soon", "label": "Due in 1h", "value": due_soon, "unit": "count"},
                {"id": "last_failed", "label": "Last run failed", "value": last_failed, "unit": "count"},
                {"id": "fired", "label": "Fired", "value": fired, "unit": "count"},
                {"id": "success_rate", "label": "Fire success", "value": success_rate, "unit": "%"},
            ],
            "series": [
                {"id": "succeeded", "label": "Succeeded", "color": "#22c55e", "axis": "count"},
                {"id": "failed", "label": "Failed", "color": "#ef4444", "axis": "count"},
                {"id": "rate", "label": "Success rate", "color": "#eab308", "axis": "percent"},
            ],
            "mix": [
                {"id": "enabled", "label": "Enabled", "value": enabled, "color": "#22c55e"},
                {"id": "disabled", "label": "Disabled", "value": max(0, total - enabled), "color": "#64748b"},
                {"id": "last_failed", "label": "Last failed", "value": last_failed, "color": "#ef4444"},
            ],
            "points": points,
            "chart_title": "Scheduled job volume and success rate",
        }


_service: Optional[AppTrendsService] = None


def get_app_trends_service() -> AppTrendsService:
    global _service
    if _service is None:
        _service = AppTrendsService()
    return _service
