"""In-process SSE manager — mirrors nexus-backend's SSEManager, trimmed.

Producers (the simulated executor) call ``broadcast(event)``. Consumers
(the FastAPI ``/stream`` endpoint) call ``subscribe(job_id)`` to receive
an async generator of SSE-formatted strings.

Event queues are per-subscriber and size-bounded; on overflow the oldest
event is dropped so a slow reader can't stall the executor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ..models import JobEvent

logger = logging.getLogger(__name__)

_QUEUE_SIZE = 256
_KEEPALIVE_SECONDS = 20.0
REDIS_URL = os.getenv("REDIS_URL", "redis://redis-svc:6379/0")
SSE_HISTORY_MAX = int(os.getenv("SSE_HISTORY_MAX", "100"))
SSE_REDIS_ENABLED = os.getenv("SSE_REDIS_ENABLED", "true").lower() in ("1", "true", "yes")

try:
    import redis as redis_sync

    REDIS_AVAILABLE = True
except ImportError:
    redis_sync = None  # type: ignore
    REDIS_AVAILABLE = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SSEManager:
    """Broadcast JobEvents to any subscribers listening for a given job."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[JobEvent | None]]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._redis_client = None
        self._redis_publish_only = False
        self._redis_listener_threads: dict[str, threading.Thread] = {}

    def _redis_channel(self, execution_id: str) -> str:
        return f"sse:execution:{execution_id}"

    def _redis_history_key(self, execution_id: str) -> str:
        return f"sse:execution:{execution_id}:history"

    def _get_redis(self):
        if not REDIS_AVAILABLE or not SSE_REDIS_ENABLED:
            return None
        if self._redis_client is None:
            self._redis_client = redis_sync.from_url(REDIS_URL, decode_responses=True)
        return self._redis_client

    def enable_redis_bridge(self, publish_only: bool = False) -> None:
        self._redis_publish_only = publish_only
        self._get_redis()

    def _publish_to_redis(self, execution_id: str, event: JobEvent) -> None:
        client = self._get_redis()
        if client is None:
            return
        payload = json.dumps(event.model_dump(mode="json"), default=str)
        try:
            pipe = client.pipeline()
            pipe.publish(self._redis_channel(execution_id), payload)
            pipe.lpush(self._redis_history_key(execution_id), payload)
            pipe.ltrim(self._redis_history_key(execution_id), 0, SSE_HISTORY_MAX - 1)
            pipe.execute()
        except Exception as exc:
            logger.warning("Redis SSE publish failed for execution %s: %s", execution_id, exc)

    def _replay_history(self, execution_id: str, q: asyncio.Queue[JobEvent | None]) -> None:
        client = self._get_redis()
        if client is None:
            return
        try:
            items = client.lrange(self._redis_history_key(execution_id), 0, SSE_HISTORY_MAX - 1)
            for raw in reversed(items or []):
                parsed = json.loads(raw)
                event = JobEvent.model_validate(parsed)
                with suppress(asyncio.QueueFull):
                    q.put_nowait(event)
        except Exception as exc:
            logger.debug("Execution SSE history replay failed for %s: %s", execution_id, exc)

    def _ensure_redis_listener(self, execution_id: str, q: asyncio.Queue[JobEvent | None]) -> None:
        if self._redis_publish_only:
            return
        if execution_id in self._redis_listener_threads:
            return

        loop = asyncio.get_event_loop()

        def _listen():
            client = self._get_redis()
            if client is None:
                return
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(self._redis_channel(execution_id))
            for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    parsed = json.loads(message["data"])
                    event = JobEvent.model_validate(parsed)

                    def _put(ev: JobEvent = event) -> None:
                        if not q.full():
                            q.put_nowait(ev)

                    loop.call_soon_threadsafe(_put)
                except Exception:
                    continue

        thread = threading.Thread(
            target=_listen,
            name=f"sse-exec-{execution_id[:12]}",
            daemon=True,
        )
        self._redis_listener_threads[execution_id] = thread
        thread.start()

    async def subscribe(self, job_id: str) -> AsyncIterator[str]:
        q: asyncio.Queue[JobEvent | None] = asyncio.Queue(maxsize=_QUEUE_SIZE)
        async with self._lock:
            self._subs[job_id].append(q)

        self._replay_history(job_id, q)
        self._ensure_redis_listener(job_id, q)

        try:
            yield _format_sse({"type": "hello", "job_id": job_id, "timestamp": _now().isoformat()})
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield _format_sse(event.model_dump(mode="json"))
        finally:
            async with self._lock:
                if q in self._subs.get(job_id, []):
                    self._subs[job_id].remove(q)
                if not self._subs[job_id]:
                    self._subs.pop(job_id, None)
            self._redis_listener_threads.pop(job_id, None)

    async def broadcast(self, event: JobEvent) -> None:
        """Send an event to every subscriber for its job_id."""
        self._publish_to_redis(event.job_id, event)
        async with self._lock:
            queues = list(self._subs.get(event.job_id, []))
        for q in queues:
            if q.full():
                with suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            with suppress(asyncio.QueueFull):
                q.put_nowait(event)

    async def close(self, job_id: str) -> None:
        """Signal all subscribers for job_id to exit their loop."""
        async with self._lock:
            queues = list(self._subs.get(job_id, []))
        for q in queues:
            with suppress(asyncio.QueueFull):
                q.put_nowait(None)

    def subscriber_count(self, job_id: str) -> int:
        return len(self._subs.get(job_id, []))


def _format_sse(payload: Any) -> str:
    """Format an event payload as TWO SSE frames.

    Emits both a named-event frame (``event: <type>\\ndata: ...``) and a
    default-channel frame (``data: ...``). Browsers route the named frame to
    ``EventSource.addEventListener('<type>', ...)`` listeners (production
    `jobStreamService` / new ``JourneyStudioV2Page``); the default frame
    fires ``EventSource.onmessage`` (legacy ``LogsDrawer``). Each frame
    carries the same JSON body so both paths see every event exactly once.
    """
    body = json.dumps(payload, default=str)
    if isinstance(payload, dict):
        name = payload.get("type") or ""
    else:
        name = ""
    if name:
        return f"event: {name}\ndata: {body}\n\ndata: {body}\n\n"
    return f"data: {body}\n\n"


def emit(event_type: str, job_id: str, step_id: str | None = None, **data: Any) -> JobEvent:
    """Helper to construct a JobEvent with current timestamp."""
    return JobEvent(
        type=event_type,
        job_id=job_id,
        step_id=step_id,
        data=data,
        timestamp=_now(),
    )
