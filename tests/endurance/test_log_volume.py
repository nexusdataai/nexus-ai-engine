"""Log-volume correctness and retrieval performance."""

from __future__ import annotations

import time

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


@pytest.mark.asyncio
async def test_500_log_lines_retrievable_and_ordered(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(JourneyCreate(
        name="log-volume",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(
                id="s1", name="S1", order=1, type="tool", tool="count_to",
                input={"n": 500, "delay_seconds": 0},
            )
        ])],
    ))
    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, j.id, job.id, timeout=15.0)

    start = time.perf_counter()
    logs = await engine.get_job_logs(j.id, job.id)
    elapsed = time.perf_counter() - start

    # Every 1..500 count line is present, in order.
    count_lines = [e for e in logs if "count " in e.message]
    assert len(count_lines) == 500
    parsed = [int(e.message.split()[1].split("/")[0]) for e in count_lines]
    assert parsed == list(range(1, 501))
    # Retrieval is fast enough (log retrieval is in-memory; should be <50ms).
    assert elapsed < 0.5, f"log retrieval took {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_search_logs_returns_matching_only(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(JourneyCreate(
        name="search",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(
                id="s1", name="S1", order=1, type="tool", tool="count_to",
                input={"n": 100, "delay_seconds": 0},
            )
        ])],
    ))
    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, j.id, job.id, timeout=10.0)

    hits = await engine.search_job_logs(j.id, job.id, "count 42/")
    assert len(hits) == 1
    assert hits[0].message.startswith("count 42/100")
