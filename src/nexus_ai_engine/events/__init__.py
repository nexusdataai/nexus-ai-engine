"""Event streaming primitives (SSE)."""

from __future__ import annotations

from .sse import SSEManager, emit

__all__ = ["SSEManager", "emit"]
