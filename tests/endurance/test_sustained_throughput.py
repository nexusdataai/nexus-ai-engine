"""Sustained job launch rate — smoke test for engine throughput."""

from __future__ import annotations

import asyncio
import time

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


@pytest.mark.asyncio
async def test_100_jobs_in_bursts(engine: InMemoryEngine) -> None:
    """Launch 100 noop jobs as 10 bursts of 10, measure total wall time."""

    j = await engine.create_journey(JourneyCreate(
        name="throughput",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(id="s1", name="S1", order=1, type="tool", tool="noop")
        ])],
    ))

    all_jobs = []
    start = time.perf_counter()
    for _ in range(10):
        burst = await asyncio.gather(*[
            engine.run_job(j.id, JobRunRequest(stage_id="stg")) for _ in range(10)
        ])
        all_jobs.extend(burst)
        await asyncio.sleep(0.005)

    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, jb.id, timeout=20.0) for jb in all_jobs
    ])
    elapsed = time.perf_counter() - start

    final = await engine.list_jobs(j.id, limit=None)
    assert len(final) == 100
    assert all(jb.status.value == "completed" for jb in final)
    # 100 noop jobs on a healthy laptop should finish under 5 s even
    # with test overhead. Tune up if CI is slow.
    assert elapsed < 10.0, f"100 jobs took {elapsed:.2f}s"
