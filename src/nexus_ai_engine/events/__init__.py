"""Event streaming primitives (SSE).

Two SSE managers ship in the library, both kept for backwards compatibility:

- :class:`SSEManager` (this module's default) — the full backend implementation:
  thread-safe, bounded queues, stale-connection cleanup, sync + async producers.
  Use this for production (DynamoDB-backed engine, journey stages, MCP tools).
- :class:`SimpleSSEManager` — the slim async-only manager used by the
  in-memory engine's reference UI.

The two are intentionally distinct: backend's stage code emits via the full
``sse_manager`` singleton and the convenience ``emit_step_status`` /
``emit_log`` / ``emit_task_progress`` / ``emit_job_complete`` helpers. The
in-memory reference engine uses ``SimpleSSEManager`` plus ``emit()``.
"""

from __future__ import annotations

from .sse import SSEManager as SimpleSSEManager
from .sse import emit
from .sse_manager import (
    SSEManager,
    emit_job_complete,
    emit_log,
    emit_step_status,
    emit_task_progress,
    sse_manager,
)

__all__ = [
    "SSEManager",
    "SimpleSSEManager",
    "emit",
    "emit_job_complete",
    "emit_log",
    "emit_step_status",
    "emit_task_progress",
    "sse_manager",
]
