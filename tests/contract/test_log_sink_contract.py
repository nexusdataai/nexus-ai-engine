"""Log-sink contract: structured log append + retrieval + search."""

from __future__ import annotations

import asyncio

from nexus_ai_engine.models import JobRunRequest, JourneyCreate, LogEntry, Stage, Step


async def _wait_terminal(adapter, journey_id, job_id, timeout=5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        job = await adapter.get_job(journey_id, job_id)
        if job and job.status.value in ("completed", "failed", "cancelled"):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("job did not terminate in time")


def test_adapter_exposes_log_methods(adapter) -> None:
    for method in ("get_job_logs", "search_job_logs", "get_job_errors"):
        assert callable(getattr(adapter, method, None)), (
            f"{type(adapter).__name__} missing async method {method!r}"
        )


async def test_logs_are_populated_after_run(adapter) -> None:
    j = await adapter.create_journey(JourneyCreate(
        name="log-contract",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(id="s1", name="S1", order=1, type="tool", tool="count_to",
                 input={"n": 5, "delay_seconds": 0})
        ])],
    ))
    job = await adapter.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    await _wait_terminal(adapter, j.id, job.id)

    logs = await adapter.get_job_logs(j.id, job.id)
    assert isinstance(logs, list) and len(logs) > 0
    for entry in logs:
        # Contract: every entry must look like a LogEntry (timestamp + level + message).
        assert isinstance(entry, LogEntry) or (
            hasattr(entry, "timestamp") and hasattr(entry, "level") and hasattr(entry, "message")
        ), entry


async def test_search_filters_logs_case_insensitively(adapter) -> None:
    j = await adapter.create_journey(JourneyCreate(
        name="search-contract",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(id="s1", name="S1", order=1, type="tool", tool="count_to",
                 input={"n": 10, "delay_seconds": 0})
        ])],
    ))
    job = await adapter.run_job(j.id, JobRunRequest(stage_id="stg"))
    await _wait_terminal(adapter, j.id, job.id)

    hits = await adapter.search_job_logs(j.id, job.id, "count 7/")
    assert len(hits) == 1
    assert "count 7/10" in hits[0].message
