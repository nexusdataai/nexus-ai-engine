"""In-process HTTP request metrics for System SLA Performance cards."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Iterable, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

SKIP_EXACT = frozenset({"/health", "/metrics", "/readiness", "/version"})
SKIP_PREFIXES = ("/api/v1/monitoring",)

_MAX_SAMPLES = 50_000


def should_skip_path(path: str) -> bool:
    if path in SKIP_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in SKIP_PREFIXES)


def percentile(values: Iterable[float], p: float) -> Optional[float]:
    xs = sorted(values)
    if not xs:
        return None
    if len(xs) == 1:
        return float(xs[0])
    rank = (p / 100.0) * (len(xs) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(xs) - 1)
    frac = rank - lo
    return round(xs[lo] * (1.0 - frac) + xs[hi] * frac, 2)


class RequestMetricsStore:
    def __init__(self, maxlen: int = _MAX_SAMPLES) -> None:
        self._samples: Deque[Tuple[float, float, int]] = deque(maxlen=maxlen)
        self._lock = Lock()

    def record(self, ts: float, duration_ms: float, status: int) -> None:
        with self._lock:
            self._samples.append((ts, duration_ms, status))

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()

    def stats(self, window_hours: int = 1) -> Dict[str, Any]:
        cutoff = time.time() - max(1, window_hours) * 3600
        with self._lock:
            window = [(ts, dur, status) for ts, dur, status in self._samples if ts >= cutoff]
        total = len(window)
        if total == 0:
            return {
                "p95_duration_ms": None,
                "p99_duration_ms": None,
                "error_rate_5xx": 0.0,
                "requests_per_second": 0.0,
                "total": 0,
            }
        durations = [dur for _, dur, _ in window]
        errors = sum(1 for _, _, status in window if status >= 500)
        span = max(1.0, time.time() - min(ts for ts, _, _ in window))
        return {
            "p95_duration_ms": percentile(durations, 95),
            "p99_duration_ms": percentile(durations, 99),
            "error_rate_5xx": errors / total,
            "requests_per_second": total / span,
            "total": total,
        }


_store = RequestMetricsStore()


def get_request_metrics_store() -> RequestMetricsStore:
    return _store


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, store: Optional[RequestMetricsStore] = None) -> None:
        super().__init__(app)
        self._store = store or _store

    async def dispatch(self, request: Request, call_next) -> Response:
        if should_skip_path(request.url.path):
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        self._store.record(time.time(), duration_ms, response.status_code)
        return response
