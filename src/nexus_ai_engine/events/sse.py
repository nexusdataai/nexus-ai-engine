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
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ..models import JobEvent

logger = logging.getLogger(__name__)

_QUEUE_SIZE = 256
_KEEPALIVE_SECONDS = 20.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SSEManager:
    """Broadcast JobEvents to any subscribers listening for a given job."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[JobEvent | None]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> AsyncIterator[str]:
        q: asyncio.Queue[JobEvent | None] = asyncio.Queue(maxsize=_QUEUE_SIZE)
        async with self._lock:
            self._subs[job_id].append(q)

        try:
            yield _format_sse({"type": "hello", "job_id": job_id, "timestamp": _now().isoformat()})
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    # Keepalive comment
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    # Shutdown signal
                    break
                yield _format_sse(event.model_dump(mode="json"))
        finally:
            async with self._lock:
                if q in self._subs.get(job_id, []):
                    self._subs[job_id].remove(q)
                if not self._subs[job_id]:
                    self._subs.pop(job_id, None)

    async def broadcast(self, event: JobEvent) -> None:
        """Send an event to every subscriber for its job_id."""
        async with self._lock:
            queues = list(self._subs.get(event.job_id, []))
        for q in queues:
            if q.full():
                with suppress(asyncio.QueueEmpty):
                    q.get_nowait()  # drop oldest
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
