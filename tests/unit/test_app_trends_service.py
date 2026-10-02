"""Unit tests for App monitoring trends."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from nexus_ai_engine.services.app_trends_service import AppTrendsService, parse_window


def test_parse_window_presets():
    assert parse_window("24h") == (24, "hour")
    assert parse_window("7d") == (168, "day")
    assert parse_window("30d") == (720, "day")
    assert parse_window("nope") == (24, "hour")


@pytest.mark.asyncio
async def test_executions_kpis_and_points(monkeypatch):
    now = datetime.now(timezone.utc)
    svc = AppTrendsService()
    monkeypatch.setattr(
        svc,
        "_list_stage_jobs",
        lambda: [
            {
                "startTime": (now - timedelta(hours=2)).isoformat(),
                "endTime": (now - timedelta(hours=1)).isoformat(),
                "status": "completed",
                "triggeredBy": "ui",
            },
            {
                "startTime": (now - timedelta(hours=3)).isoformat(),
                "endTime": (now - timedelta(hours=2)).isoformat(),
                "status": "failed",
                "triggeredBy": "ui",
            },
        ],
    )

    async def no_dsl(_cutoff):
        return []

    monkeypatch.setattr(svc, "_dsl_events", no_dsl)
    data = await svc.get_trends("executions", window="24h")
    assert data["tab"] == "executions"
    ids = {k["id"] for k in data["kpis"]}
    assert {"submitted", "succeeded", "failed", "success_rate"} <= ids
    assert next(k for k in data["kpis"] if k["id"] == "submitted")["value"] == 2
    assert next(k for k in data["kpis"] if k["id"] == "succeeded")["value"] == 1
    assert next(k for k in data["kpis"] if k["id"] == "failed")["value"] == 1
    assert data["points"]
    assert any(p["succeeded"] or p["failed"] for p in data["points"])


@pytest.mark.asyncio
async def test_schedules_kpis_from_jobs_and_rows(monkeypatch):
    now = datetime.now(timezone.utc)

    class FakeScheduler:
        def list_schedules(self):
            return [
                {
                    "enabled": True,
                    "nextRunAt": (now + timedelta(minutes=10)).isoformat(),
                    "lastJobStatus": "completed",
                },
                {"enabled": False, "nextRunAt": None, "lastJobStatus": "failed"},
            ]

        @classmethod
        def get_instance(cls):
            return FakeScheduler()

    import nexus_ai_engine.services.scheduler_service as sched_mod

    monkeypatch.setattr(sched_mod, "SchedulerService", FakeScheduler)

    svc = AppTrendsService()
    monkeypatch.setattr(
        svc,
        "_list_stage_jobs",
        lambda: [
            {
                "startTime": (now - timedelta(hours=1)).isoformat(),
                "endTime": now.isoformat(),
                "status": "completed",
                "triggeredBy": "scheduler",
            }
        ],
    )
    data = await svc.get_trends("schedules", window="24h")
    assert data["tab"] == "schedules"
    assert next(k for k in data["kpis"] if k["id"] == "total")["value"] == 2
    assert next(k for k in data["kpis"] if k["id"] == "enabled")["value"] == 1
    assert next(k for k in data["kpis"] if k["id"] == "due_soon")["value"] == 1
    assert next(k for k in data["kpis"] if k["id"] == "last_failed")["value"] == 1
    assert next(k for k in data["kpis"] if k["id"] == "fired")["value"] == 1
