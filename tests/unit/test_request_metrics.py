"""Unit tests for in-process HTTP request metrics."""

import time

from nexus_ai_engine.server.request_metrics import (
    RequestMetricsStore,
    percentile,
    should_skip_path,
)


def test_skips_health_metrics_and_monitoring_paths():
    assert should_skip_path("/health")
    assert should_skip_path("/metrics")
    assert should_skip_path("/readiness")
    assert should_skip_path("/version")
    assert should_skip_path("/api/v1/monitoring/slas")
    assert should_skip_path("/api/v1/monitoring/slas/performance")
    assert not should_skip_path("/api/v1/settings")
    assert not should_skip_path("/api/v1/journeys")


def test_percentile_p95_p99():
    values = [float(i) for i in range(1, 101)]
    p95 = percentile(values, 95)
    p99 = percentile(values, 99)
    assert p95 is not None and 94 <= p95 <= 96
    assert p99 is not None and 98 <= p99 <= 100
    assert percentile([], 95) is None


def test_store_stats_error_rate_and_total():
    store = RequestMetricsStore()
    now = time.time()
    store.record(now, 10.0, 200)
    store.record(now, 20.0, 200)
    store.record(now, 30.0, 500)
    stats = store.stats(window_hours=1)
    assert stats["total"] == 3
    assert stats["error_rate_5xx"] == 1 / 3
    assert stats["p95_duration_ms"] is not None
    assert stats["p99_duration_ms"] is not None
    assert stats["requests_per_second"] > 0
