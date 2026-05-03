"""Many jobs on a single journey — the baseline concurrency test."""

from __future__ import annotations

import asyncio

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


async def _make(engine: InMemoryEngine, tool: str, input_: dict | None = None):
    return await engine.create_journey(
        JourneyCreate(
            name="many-jobs",
            stages=[Stage(id="stg", name="S", order=1, steps=[
                Step(id="s1", name="S1", order=1, type="tool", tool=tool, input=input_ or {})
            ])],
        )
    )


@pytest.mark.asyncio
async def test_fifty_noop_jobs(engine: InMemoryEngine) -> None:
    j = await _make(engine, "noop")
    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg")) for _ in range(50)
    ])
    assert all(jb is not None for jb in jobs)
    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, jb.id, timeout=15.0) for jb in jobs
    ])
    final = await engine.list_jobs(j.id, limit=None)
    assert len(final) == 50
    assert all(jb.status.value == "completed" for jb in final)


@pytest.mark.asyncio
async def test_thirty_sleep_jobs_complete(engine: InMemoryEngine) -> None:
    j = await _make(engine, "sleep", {"seconds": 0.1})
    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg")) for _ in range(30)
    ])
    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, jb.id, timeout=15.0) for jb in jobs
    ])
    # With 30 jobs of 0.1s sleep running concurrently, total wall time
    # should be close to 0.1s (not 3.0s). Just verify all completed; the
    # engine doesn't enforce concurrency limits yet so the assertion is
    # correctness, not timing.
    final = await engine.list_jobs(j.id, limit=None)
    assert len(final) == 30
    assert all(jb.status.value == "completed" for jb in final)
