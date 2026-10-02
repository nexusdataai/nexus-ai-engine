"""Unit tests for SlaMonitoringService summary aggregation."""

from __future__ import annotations

import pytest

from nexus_ai_engine.services.sla_monitoring_service import PILLAR_IDS, SlaMonitoringService


@pytest.mark.asyncio
async def test_get_summary_returns_five_pillars(monkeypatch):
    svc = SlaMonitoringService()
    monkeypatch.setattr(svc, "_request_stats", lambda hours: {
        "p95_duration_ms": 120.0,
        "p99_duration_ms": 180.0,
        "error_rate_5xx": 0.0,
        "requests_per_second": 2.5,
        "total": 10,
    })
    monkeypatch.setattr(svc, "_system_cpu", lambda: 20.0)
    monkeypatch.setattr(svc, "_system_memory", lambda: 40.0)
    monkeypatch.setattr(svc, "_dynamodb_probe_ms", lambda: 8.0)
    monkeypatch.setattr(svc, "_dynamodb_reachable", lambda: True)
    monkeypatch.setattr(svc, "_redis_ping", lambda: (3.0, True))
    monkeypatch.setattr(svc, "_s3_probe_ms", lambda: 15.0)
    monkeypatch.setattr(svc, "_s3_reachable", lambda: True)
    monkeypatch.setattr(svc, "_health_uptime_pct", lambda hours: 100.0)
    monkeypatch.setattr(svc, "_ready_ratio", lambda: 100.0)
    monkeypatch.setattr(svc, "_pod_restart_count", lambda: 0.0)
    monkeypatch.setattr(svc, "_queue_lag_ratio_pct", lambda: 10.0)

    async def fake_jobs(hours):
        return {"throughput": {"submitted": 4, "succeeded": 4, "failed": 0}}

    monkeypatch.setattr(svc, "_job_metrics", fake_jobs)
    monkeypatch.setattr(svc, "_read_latest_snapshot", lambda window_hours: None)
    monkeypatch.setattr(svc, "_write_snapshot", lambda snapshot: None)

    data = await svc.get_summary(window_hours=1)
    assert set(data["pillars"].keys()) == set(PILLAR_IDS)
    assert data["overall_score"] is not None
    assert data["overall_status"] in {"healthy", "warning", "critical", "unknown"}
    for pillar in PILLAR_IDS:
        assert "score" in data["pillars"][pillar]
        assert "status" in data["pillars"][pillar]
