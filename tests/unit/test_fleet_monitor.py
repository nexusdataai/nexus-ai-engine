"""Unit tests for fleet monitor service."""

from __future__ import annotations

from uuid import uuid4

import pytest

from nexus_ai_engine.contracts.execution_state import ExecutionState, ExecutionStatus
from nexus_ai_engine.execution.runtime_service import ExecutionRuntimeService
from nexus_ai_engine.fleet.service import FleetMonitorService, _parse_window_hours, _percentile


def test_parse_window_hours() -> None:
    assert _parse_window_hours("24h") == 24
    assert _parse_window_hours("12") == 12
    assert _parse_window_hours(None) == 24
    assert _parse_window_hours("bad") == 24


def test_percentile() -> None:
    assert _percentile([], 95) is None
    assert _percentile([10.0, 20.0, 30.0], 95) == 30.0


@pytest.mark.asyncio
async def test_summary_counts_in_memory() -> None:
    runtime = ExecutionRuntimeService()
    service = FleetMonitorService(runtime=runtime)
    eid = uuid4()
    runtime.manager._executions[eid] = ExecutionState(
        execution_id=eid,
        journey_id="demo",
        journey_version=1,
        tenant_id=str(uuid4()),
        status=ExecutionStatus.RUNNING,
        graph_snapshot_id=uuid4(),
    )
    summary = await service.summary()
    assert summary["active"] == 1
    assert summary["queued"] == 0
    assert summary["dsl_executions_active"] == 1
    assert summary["stage_jobs_active"] == 0


def test_parse_job_time_iso() -> None:
    from nexus_ai_engine.fleet.service import _parse_job_time

    parsed = _parse_job_time("2026-08-30T12:00:00Z")
    assert parsed is not None
    assert parsed.year == 2026


@pytest.mark.asyncio
async def test_workers_queue_mode_lists_job_workers(monkeypatch) -> None:
    runtime = ExecutionRuntimeService()
    service = FleetMonitorService(runtime=runtime)

    monkeypatch.setattr(
        "nexus_ai_engine.services.job_queue_service.is_queue_mode",
        lambda: True,
    )

    class _FakeWorkers:
        def list_workers(self):
            return {
                "workers": [
                    {
                        "worker_id": "ai-engine-dev-job-worker-abc",
                        "consumer_name": "ai-engine-worker-ai-engine-dev-job-worker-abc-1a2b3c",
                        "status": "idle",
                        "current_job": None,
                        "last_seen": "2026-08-30T00:00:00+00:00",
                    }
                ],
                "generated_at": "2026-08-30T00:00:00+00:00",
            }

    monkeypatch.setattr(
        "nexus_ai_engine.services.worker_management_service.get_worker_management_service",
        lambda: _FakeWorkers(),
    )

    body = await service.workers()
    assert len(body["workers"]) == 1
    assert body["workers"][0]["role"] == "job-worker"
    assert body["workers"][0]["worker_id"] == "ai-engine-dev-job-worker-abc"
    assert body["workers"][0]["status"] == "idle"


@pytest.mark.asyncio
async def test_workers_queue_mode_empty_does_not_count_api_pod(monkeypatch) -> None:
    runtime = ExecutionRuntimeService()
    service = FleetMonitorService(runtime=runtime, _hostname="api-pod-1")
    monkeypatch.setattr(
        "nexus_ai_engine.services.job_queue_service.is_queue_mode",
        lambda: True,
    )

    class _EmptyWorkers:
        def list_workers(self):
            return {"workers": [], "generated_at": "2026-08-30T00:00:00+00:00"}

    monkeypatch.setattr(
        "nexus_ai_engine.services.worker_management_service.get_worker_management_service",
        lambda: _EmptyWorkers(),
    )
    body = await service.workers()
    assert body["workers"] == []


@pytest.mark.asyncio
async def test_workers_inline_mode_includes_api_pod() -> None:
    runtime = ExecutionRuntimeService()
    service = FleetMonitorService(runtime=runtime, _hostname="api-pod-1")
    body = await service.workers()
    assert body["workers"][0]["role"] == "api"
    assert body["workers"][0]["worker_id"] == "api-pod-1"
