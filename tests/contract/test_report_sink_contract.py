"""Report-sink contract: per-job report creation + journey aggregation."""

from __future__ import annotations

import asyncio

from nexus_ai_engine.models import (
    JobRunRequest,
    JourneyCreate,
    ReportCreate,
    Stage,
    Step,
)


async def _wait_terminal(adapter, journey_id, job_id, timeout=5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        job = await adapter.get_job(journey_id, job_id)
        if job and job.status.value in ("completed", "failed", "cancelled"):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("job did not terminate in time")


def test_adapter_exposes_report_methods(adapter) -> None:
    for method in ("list_job_reports", "create_job_report", "aggregate_report"):
        assert callable(getattr(adapter, method, None)), (
            f"{type(adapter).__name__} missing async method {method!r}"
        )


async def test_create_and_list_report_round_trip(adapter) -> None:
    j = await adapter.create_journey(JourneyCreate(
        name="report-contract",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(id="s1", name="S1", order=1, type="tool", tool="noop")
        ])],
    ))
    job = await adapter.run_job(j.id, JobRunRequest(stage_id="stg"))
    await _wait_terminal(adapter, j.id, job.id)

    created = await adapter.create_job_report(
        j.id, job.id,
        ReportCreate(step_id="s1", title="Contract Report", summary="ok", data={"x": 1}),
    )
    assert created is not None and created.title == "Contract Report"

    reports = await adapter.list_job_reports(j.id, job.id)
    assert len(reports) == 1 and reports[0].id == created.id


async def test_aggregate_report_returns_consistent_shape(adapter) -> None:
    j = await adapter.create_journey(JourneyCreate(
        name="aggregate-contract",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(id="s1", name="S1", order=1, type="tool", tool="noop")
        ])],
    ))
    # One successful job so totals have something to report on.
    job = await adapter.run_job(j.id, JobRunRequest(stage_id="stg"))
    await _wait_terminal(adapter, j.id, job.id)

    report = await adapter.aggregate_report(j.id)
    assert report is not None
    assert report.total_jobs >= 1
    assert 0 <= report.success_rate <= 100
    # Contract: per_stage dict is keyed by stage id (even for empty journeys).
    assert "stg" in report.per_stage
