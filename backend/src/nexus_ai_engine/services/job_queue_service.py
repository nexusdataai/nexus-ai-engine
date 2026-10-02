"""Redis Streams job queue for distributed journey and DSL execution."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from loguru import logger

JobKind = Literal["transformation", "dsl_execution"]

REDIS_URL = os.getenv("REDIS_URL", "redis://redis-svc:6379/0")
JOB_STREAM_KEY = os.getenv("JOB_STREAM_KEY", "ai-engine:jobs")
JOB_CONSUMER_GROUP = os.getenv("JOB_CONSUMER_GROUP", "ai-engine-workers")
JOB_ACTIVE_COUNTER_KEY = os.getenv("JOB_ACTIVE_COUNTER_KEY", "ai-engine:jobs:active")
JOB_WAITING_SET_KEY = os.getenv("JOB_WAITING_SET_KEY", "ai-engine:jobs:waiting")
JOB_CANCELLED_SET_KEY = os.getenv("JOB_CANCELLED_SET_KEY", "ai-engine:jobs:cancelled")

try:
    import redis as redis_sync

    REDIS_AVAILABLE = True
except ImportError:
    redis_sync = None  # type: ignore
    REDIS_AVAILABLE = False


@dataclass
class QueuedJob:
    stream_id: str
    job_id: str
    journey_id: str
    job_kind: JobKind = "transformation"
    stage_id: str = ""
    stage_ids: List[str] = field(default_factory=list)
    triggered_by: str = "queue"
    reason: str = ""
    job_config: Dict[str, Any] = field(default_factory=dict)


def get_max_global_jobs() -> int:
    from .job_execution_config_service import get_job_execution_config

    return get_job_execution_config().get_max_global_jobs()


def get_worker_threads() -> int:
    from .job_execution_config_service import get_job_execution_config

    return get_job_execution_config().get_worker_threads()


def get_live_consumer_count() -> int:
    """Consumers that are not idle-and-empty (old pods leave stale XINFO entries)."""
    try:
        consumers = _client().xinfo_consumers(JOB_STREAM_KEY, JOB_CONSUMER_GROUP)
        live = 0
        for consumer in consumers or []:
            idle_ms = int(consumer.get("idle") or 0)
            pending = int(consumer.get("pending") or 0)
            if consumer_health(idle_ms, pending) != "stale":
                live += 1
        return live
    except Exception:
        return get_consumer_count()


def get_running_capacity() -> int:
    return min(get_max_global_jobs(), get_live_consumer_count() * get_worker_threads())


def is_queue_mode() -> bool:
    from .job_execution_config_service import get_job_execution_config

    return get_job_execution_config().is_queue_mode()


def redis_available() -> bool:
    return REDIS_AVAILABLE and bool(os.getenv("REDIS_URL", REDIS_URL))


def _client():
    if not REDIS_AVAILABLE:
        raise RuntimeError("redis package not available")
    return redis_sync.from_url(REDIS_URL, decode_responses=True)


def ensure_consumer_group() -> None:
    client = _client()
    try:
        client.xgroup_create(JOB_STREAM_KEY, JOB_CONSUMER_GROUP, id="0", mkstream=True)
        logger.info("Created Redis consumer group %s on %s", JOB_CONSUMER_GROUP, JOB_STREAM_KEY)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def get_queue_depth() -> int:
    try:
        return int(_client().xlen(JOB_STREAM_KEY))
    except Exception:
        return 0


def get_pending_count() -> int:
    try:
        pending = _client().xpending(JOB_STREAM_KEY, JOB_CONSUMER_GROUP)
        if isinstance(pending, dict):
            return int(pending.get("pending", 0))
        if pending:
            return int(pending[0])
        return 0
    except Exception:
        return 0


def get_active_job_count() -> int:
    try:
        val = _client().get(JOB_ACTIVE_COUNTER_KEY)
        return int(val or 0)
    except Exception:
        return 0


def _undelivered_count(last_delivered_id: str, limit: int = 1000) -> int:
    last_id = last_delivered_id or "0-0"
    try:
        if last_id in ("0-0", "0", ""):
            return int(_client().xlen(JOB_STREAM_KEY) or 0)
        entries = _client().xrange(
            JOB_STREAM_KEY,
            min=f"({last_id}",
            max="+",
            count=limit,
        )
        return len(entries or [])
    except Exception:
        return 0


def _mark_waiting(stream_id: str) -> None:
    try:
        _client().sadd(JOB_WAITING_SET_KEY, stream_id)
    except Exception as exc:
        logger.warning("Failed to record waiting job %s: %s", stream_id, exc)


def _unmark_waiting(stream_id: str) -> None:
    try:
        _client().srem(JOB_WAITING_SET_KEY, stream_id)
    except Exception as exc:
        logger.warning("Failed to clear waiting job %s: %s", stream_id, exc)


def get_waiting_count() -> int:
    try:
        return int(_client().scard(JOB_WAITING_SET_KEY) or 0)
    except Exception:
        return get_consumer_lag()


def get_consumer_lag() -> int:
    """Messages in the stream not yet delivered to the consumer group.

    Redis 7+ exposes XINFO GROUPS ``lag``. Redis 6 does not — fall back to
    counting entries after ``last-delivered-id`` so waiting jobs stay visible.
    """
    try:
        groups = _client().xinfo_groups(JOB_STREAM_KEY)
        for group in groups or []:
            if group.get("name") != JOB_CONSUMER_GROUP:
                continue
            if "lag" in group and group.get("lag") is not None:
                return int(group.get("lag") or 0)
            return _undelivered_count(str(group.get("last-delivered-id") or "0-0"))
        return int(_client().xlen(JOB_STREAM_KEY) or 0)
    except Exception:
        return 0


def get_stage_jobs_queued() -> int:
    """Stage/DSL jobs waiting in Redis (not actively executing)."""
    return get_waiting_count()


def get_consumer_count() -> int:
    try:
        consumers = _client().xinfo_consumers(JOB_STREAM_KEY, JOB_CONSUMER_GROUP)
        return len(consumers or [])
    except Exception:
        return 0


def _group_info() -> Dict[str, Any]:
    try:
        groups = _client().xinfo_groups(JOB_STREAM_KEY)
        for group in groups or []:
            if group.get("name") == JOB_CONSUMER_GROUP:
                return group
    except Exception:
        pass
    return {}


def _stream_entry_fields(stream_id: str) -> Dict[str, str]:
    try:
        entries = _client().xrange(JOB_STREAM_KEY, min=stream_id, max=stream_id, count=1)
        if entries:
            return entries[0][1]
    except Exception:
        pass
    return {}


def _job_to_dict(
    job: QueuedJob,
    *,
    state: str,
    consumer_name: str = "",
    idle_ms: int = 0,
    enqueued_at: int | None = None,
) -> Dict[str, Any]:
    return {
        "stream_id": job.stream_id,
        "job_id": job.job_id,
        "journey_id": job.journey_id,
        "job_kind": job.job_kind,
        "stage_id": job.stage_id,
        "stage_ids": job.stage_ids,
        "triggered_by": job.triggered_by,
        "reason": job.reason,
        "state": state,
        "consumer_name": consumer_name,
        "idle_ms": idle_ms,
        "enqueued_at": enqueued_at,
    }


def get_queue_snapshot() -> Dict[str, Any]:
    from datetime import datetime, timezone

    lag = get_waiting_count()
    pending = get_pending_count()
    active = get_active_job_count()
    return {
        "lag": lag,
        "pending": pending,
        "active": active,
        "queued": get_stage_jobs_queued(),
        "max_global": get_max_global_jobs(),
        "consumer_count": get_consumer_count(),
        "worker_threads": get_worker_threads(),
        "running_capacity": get_running_capacity(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def list_pending_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    client = _client()
    active = get_active_job_count()
    try:
        pending_entries = client.xpending_range(
            JOB_STREAM_KEY,
            JOB_CONSUMER_GROUP,
            min="-",
            max="+",
            count=limit,
        )
    except Exception:
        return []

    rows: List[tuple[int, Dict[str, Any]]] = []
    for item in pending_entries or []:
        stream_id = item.get("message_id") or item[0]
        consumer = item.get("consumer") or (item[1] if len(item) > 1 else "")
        idle_ms = int(item.get("time_since_delivered") or (item[3] if len(item) > 3 else 0))
        fields = _stream_entry_fields(stream_id)
        if not fields:
            continue
        job = _parse_queued_job(stream_id, fields)
        enqueued_raw = fields.get("enqueued_at")
        enqueued_at = int(enqueued_raw) if enqueued_raw and str(enqueued_raw).isdigit() else None
        rows.append(
            (
                idle_ms,
                _job_to_dict(
                    job,
                    state="claimed",
                    consumer_name=consumer,
                    idle_ms=idle_ms,
                    enqueued_at=enqueued_at,
                ),
            )
        )

    rows.sort(key=lambda r: r[0])
    running_slots = max(0, min(active, len(rows)))
    result: List[Dict[str, Any]] = []
    for idx, (_idle, row) in enumerate(rows):
        if idx < running_slots:
            row = {**row, "state": "running"}
        result.append(row)
    return result


def list_waiting_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """Unclaimed jobs. Prefers the waiting set written on enqueue."""
    pending_ids = {j["stream_id"] for j in list_pending_jobs(limit=500)}
    from_set = _list_waiting_from_set(limit, pending_ids)
    if from_set:
        return from_set
    return _list_waiting_from_stream(limit, pending_ids)


def _list_waiting_from_set(
    limit: int, pending_ids: set[str]
) -> List[Dict[str, Any]]:
    try:
        raw = _client().smembers(JOB_WAITING_SET_KEY)
    except Exception:
        return []
    if not isinstance(raw, (list, set, tuple, frozenset)):
        return []
    ids = sorted(str(item) for item in raw)
    result: List[Dict[str, Any]] = []
    for stream_id in ids:
        if stream_id in pending_ids:
            _unmark_waiting(stream_id)
            continue
        fields = _stream_entry_fields(stream_id)
        if not fields:
            _unmark_waiting(stream_id)
            continue
        job = _parse_queued_job(stream_id, fields)
        enqueued_raw = fields.get("enqueued_at")
        enqueued_at = int(enqueued_raw) if enqueued_raw and str(enqueued_raw).isdigit() else None
        result.append(_job_to_dict(job, state="waiting", enqueued_at=enqueued_at))
        if len(result) >= limit:
            break
    return result


def _list_waiting_from_stream(
    limit: int, pending_ids: set[str]
) -> List[Dict[str, Any]]:
    group = _group_info()
    last_id = str(group.get("last-delivered-id") or "0-0")
    fetch = max(limit, 1) + len(pending_ids)
    try:
        if last_id in ("0-0", "0", ""):
            entries = _client().xrange(JOB_STREAM_KEY, min="-", max="+", count=fetch)
        else:
            entries = _client().xrange(
                JOB_STREAM_KEY,
                min=f"({last_id}",
                max="+",
                count=fetch,
            )
    except Exception:
        return []

    result: List[Dict[str, Any]] = []
    for stream_id, fields in entries or []:
        if stream_id in pending_ids:
            continue
        job = _parse_queued_job(stream_id, fields)
        enqueued_raw = fields.get("enqueued_at")
        enqueued_at = int(enqueued_raw) if enqueued_raw and str(enqueued_raw).isdigit() else None
        result.append(_job_to_dict(job, state="waiting", enqueued_at=enqueued_at))
        if len(result) >= limit:
            break
    return result


def list_queue_jobs(
    *,
    state: str = "all",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    limit = max(1, min(limit, 200))
    if state == "waiting":
        return list_waiting_jobs(limit)
    if state in ("claimed", "running"):
        jobs = list_pending_jobs(limit)
        return [j for j in jobs if j["state"] == state]
    if state == "pending":
        return list_pending_jobs(limit)

    waiting = list_waiting_jobs(limit)
    pending = list_pending_jobs(limit)
    combined = waiting + pending
    return combined[:limit]


def get_queue_timeline(limit: int = 30) -> List[Dict[str, Any]]:
    from datetime import datetime, timezone

    limit = max(1, min(limit, 100))
    try:
        entries = _client().xrevrange(JOB_STREAM_KEY, max="+", min="-", count=limit)
    except Exception:
        return []

    pending_ids = {j["stream_id"] for j in list_pending_jobs(limit=500)}
    timeline: List[Dict[str, Any]] = []
    for stream_id, fields in entries or []:
        job = _parse_queued_job(stream_id, fields)
        enqueued_raw = fields.get("enqueued_at")
        enqueued_at = int(enqueued_raw) if enqueued_raw and enqueued_raw.isdigit() else None
        event = "dequeued" if stream_id not in pending_ids else "enqueued"
        timeline.append(
            {
                "stream_id": stream_id,
                "job_id": job.job_id,
                "journey_id": job.journey_id,
                "job_kind": job.job_kind,
                "event": event,
                "enqueued_at": enqueued_at,
                "timestamp": datetime.fromtimestamp(enqueued_at, tz=timezone.utc).isoformat()
                if enqueued_at
                else None,
            }
        )
    return timeline


def consumer_health(idle_ms: int, pending_count: int) -> str:
    """Map Redis consumer idle/pending to dashboard health.

    XINFO idle is time since the last group command, not process liveness.
    A worker executing a job does not call XREADGROUP, so idle_ms grows
    while the pod is healthy and busy. Pending entries mean the worker
    still owns work and must not be marked stale.
    """
    if pending_count > 0:
        return "healthy"
    if idle_ms > 120_000:
        return "stale"
    # Ready and recently active. The dashboard badge treats only
    # "healthy" as up; "idle" rendered as Failed on the previous UI.
    return "healthy"


def list_consumers() -> List[Dict[str, Any]]:
    try:
        consumers = _client().xinfo_consumers(JOB_STREAM_KEY, JOB_CONSUMER_GROUP)
    except Exception:
        return []

    pending_by_consumer: Dict[str, List[Dict[str, Any]]] = {}
    for job in list_pending_jobs(limit=200):
        name = job.get("consumer_name") or ""
        pending_by_consumer.setdefault(name, []).append(job)

    rows: List[Dict[str, Any]] = []
    for consumer in consumers or []:
        name = consumer.get("name", "")
        idle_ms = int(consumer.get("idle") or 0)
        pending_count = int(consumer.get("pending") or 0)
        jobs = pending_by_consumer.get(name, [])
        current_job = jobs[0] if jobs else None
        status = consumer_health(idle_ms, pending_count)
        rows.append(
            {
                "consumer_name": name,
                "pending_jobs": pending_count,
                "idle_ms": idle_ms,
                "status": status,
                "current_job": (
                    {
                        "job_id": current_job["job_id"],
                        "journey_id": current_job["journey_id"],
                        "idle_ms": current_job.get("idle_ms", 0),
                    }
                    if current_job
                    else None
                ),
            }
        )
    return rows


def _reserve_active_slot() -> bool:
    client = _client()
    max_jobs = get_max_global_jobs()
    count = int(client.incr(JOB_ACTIVE_COUNTER_KEY))
    if count > max_jobs:
        client.decr(JOB_ACTIVE_COUNTER_KEY)
        return False
    return True


def _release_active_slot() -> None:
    try:
        client = _client()
        remaining = client.decr(JOB_ACTIVE_COUNTER_KEY)
        if remaining is not None and int(remaining) < 0:
            client.set(JOB_ACTIVE_COUNTER_KEY, 0)
    except Exception as exc:
        logger.warning("Failed to release active job slot: %s", exc)


def _parse_queued_job(stream_id: str, fields: Dict[str, str]) -> QueuedJob:
    job_config_raw = fields.get("job_config") or "{}"
    stage_ids_raw = fields.get("stage_ids") or "[]"
    try:
        job_config = json.loads(job_config_raw)
    except json.JSONDecodeError:
        job_config = {}
    try:
        stage_ids = json.loads(stage_ids_raw)
        if not isinstance(stage_ids, list):
            stage_ids = []
    except json.JSONDecodeError:
        stage_ids = []
    job_kind = fields.get("job_kind") or "transformation"
    if job_kind not in ("transformation", "dsl_execution"):
        job_kind = "transformation"
    return QueuedJob(
        stream_id=stream_id,
        job_id=fields["job_id"],
        journey_id=fields.get("journey_id") or "",
        job_kind=job_kind,  # type: ignore[arg-type]
        stage_id=fields.get("stage_id") or "",
        stage_ids=stage_ids,
        triggered_by=fields.get("triggered_by") or "queue",
        reason=fields.get("reason") or "",
        job_config=job_config,
    )


def _stream_payload(
    *,
    job_id: str,
    journey_id: str,
    job_kind: JobKind = "transformation",
    stage_id: str = "",
    stage_ids: Optional[List[str]] = None,
    triggered_by: str = "system",
    reason: str = "",
    job_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    return {
        "job_id": job_id,
        "journey_id": journey_id,
        "job_kind": job_kind,
        "stage_id": stage_id or "",
        "stage_ids": json.dumps(stage_ids or []),
        "triggered_by": triggered_by,
        "reason": reason or "",
        "job_config": json.dumps(job_config or {}),
        "enqueued_at": str(int(time.time())),
    }


def enqueue_job(
    *,
    job_id: str,
    journey_id: str,
    job_kind: JobKind = "transformation",
    stage_id: str = "",
    stage_ids: Optional[List[str]] = None,
    triggered_by: str = "system",
    reason: str = "",
    job_config: Optional[Dict[str, Any]] = None,
) -> str:
    ensure_consumer_group()
    stream_id = _client().xadd(
        JOB_STREAM_KEY,
        _stream_payload(
            job_id=job_id,
            journey_id=journey_id,
            job_kind=job_kind,
            stage_id=stage_id,
            stage_ids=stage_ids,
            triggered_by=triggered_by,
            reason=reason,
            job_config=job_config,
        ),
    )
    _mark_waiting(stream_id)
    logger.info("Enqueued %s job %s on stream %s", job_kind, job_id, stream_id)
    return stream_id


def enqueue_jobs(jobs: List[Dict[str, Any]]) -> List[str]:
    """XADD every job in one pipeline so the waiting set fills before workers claim."""
    if not jobs:
        return []
    ensure_consumer_group()
    pipe = _client().pipeline()
    for job in jobs:
        pipe.xadd(
            JOB_STREAM_KEY,
            _stream_payload(
                job_id=str(job.get("job_id") or ""),
                journey_id=str(job.get("journey_id") or ""),
                job_kind=job.get("job_kind") or "transformation",
                stage_id=str(job.get("stage_id") or ""),
                stage_ids=job.get("stage_ids") or [],
                triggered_by=str(job.get("triggered_by") or "system"),
                reason=str(job.get("reason") or ""),
                job_config=job.get("job_config") or {},
            ),
        )
    stream_ids = [str(sid) for sid in (pipe.execute() or []) if sid]
    if stream_ids:
        _client().sadd(JOB_WAITING_SET_KEY, *stream_ids)
    logger.info("Enqueued %s jobs onto the wait stream", len(stream_ids))
    return stream_ids


def claim_job(consumer_name: str, block_ms: int = 5000) -> Optional[QueuedJob]:
    ensure_consumer_group()
    entries = _client().xreadgroup(
        JOB_CONSUMER_GROUP,
        consumer_name,
        {JOB_STREAM_KEY: ">"},
        count=1,
        block=block_ms,
    )
    if not entries:
        return None
    _stream_name, messages = entries[0]
    stream_id, fields = messages[0]
    _unmark_waiting(stream_id)
    return _parse_queued_job(stream_id, fields)


def ack_job(stream_id: str) -> None:
    _unmark_waiting(stream_id)
    _client().xack(JOB_STREAM_KEY, JOB_CONSUMER_GROUP, stream_id)


def mark_job_cancelled(job_id: str) -> None:
    try:
        _client().sadd(JOB_CANCELLED_SET_KEY, job_id)
    except Exception as exc:
        logger.warning("Failed to mark job %s cancelled: %s", job_id, exc)


def is_cancel_requested(job_id: str) -> bool:
    try:
        return bool(_client().sismember(JOB_CANCELLED_SET_KEY, job_id))
    except Exception:
        return False


def drop_queue_job(job_id: str) -> int:
    """Remove a job from the wait/pending stream so workers do not pick it up."""
    mark_job_cancelled(job_id)
    removed = 0
    try:
        for row in list_queue_jobs(state="all", limit=200):
            if row.get("job_id") != job_id:
                continue
            stream_id = str(row.get("stream_id") or "")
            if not stream_id:
                continue
            _unmark_waiting(stream_id)
            try:
                _client().xack(JOB_STREAM_KEY, JOB_CONSUMER_GROUP, stream_id)
            except Exception:
                pass
            try:
                _client().xdel(JOB_STREAM_KEY, stream_id)
            except Exception:
                pass
            removed += 1
    except Exception as exc:
        logger.warning("Failed to drop queue job %s: %s", job_id, exc)
    return removed


def reclaim_stale_jobs(
    consumer_name: str, min_idle_ms: int = 120_000, limit: int = 10
) -> List[QueuedJob]:
    if limit <= 0:
        return []
    ensure_consumer_group()
    client = _client()
    reclaimed: List[QueuedJob] = []
    try:
        pending = client.xpending_range(
            JOB_STREAM_KEY,
            JOB_CONSUMER_GROUP,
            min="-",
            max="+",
            count=max(limit, 10),
        )
    except Exception:
        return reclaimed

    for item in pending or []:
        if len(reclaimed) >= limit:
            break
        stream_id = item["message_id"]
        idle_ms = item.get("time_since_delivered", 0)
        if idle_ms < min_idle_ms:
            continue
        try:
            claimed = client.xclaim(
                JOB_STREAM_KEY,
                JOB_CONSUMER_GROUP,
                consumer_name,
                min_idle_time=min_idle_ms,
                message_ids=[stream_id],
            )
        except Exception:
            continue
        for msg_id, fields in claimed or []:
            if len(reclaimed) >= limit:
                break
            _unmark_waiting(msg_id)
            reclaimed.append(_parse_queued_job(msg_id, fields))
    return reclaimed


class ActiveJobGuard:
    """Context manager to enforce global active job cap in workers."""

    def __enter__(self):
        if not _reserve_active_slot():
            raise RuntimeError(
                f"Global job capacity ({get_max_global_jobs()}) reached; retry later"
            )
        return self

    def __exit__(self, exc_type, exc, tb):
        _release_active_slot()
        return False


def make_consumer_name(prefix: str = "ai-engine-worker") -> str:
    host = os.getenv("HOSTNAME", "local")
    return f"{prefix}-{host}-{uuid.uuid4().hex[:6]}"
