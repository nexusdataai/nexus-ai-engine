"""Heavy scenarios, skipped by default; run with `make test-endurance-full`."""

from __future__ import annotations

import asyncio
import resource

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


@pytest.mark.heavy
@pytest.mark.asyncio
async def test_heavy_500_jobs_no_runaway_memory(engine: InMemoryEngine) -> None:
    """Run 500 noop jobs back-to-back; process RSS growth stays bounded.

    RSS is measured via resource.getrusage on Linux (ru_maxrss is KB).
    Allow up to 100 MiB of growth during the whole run. Tightens once
    we've gathered actual baseline numbers in CI.
    """
    j = await engine.create_journey(JourneyCreate(
        name="heavy-memory",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(id="s1", name="S1", order=1, type="tool", tool="noop")
        ])],
    ))

    rss_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg")) for _ in range(500)
    ])
    assert all(jb is not None for jb in jobs)
    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, jb.id, timeout=60.0) for jb in jobs
    ])

    rss_end = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KB on Linux, bytes on macOS. Normalize to KiB.
    growth_kb = max(0, rss_end - rss_start)
    assert growth_kb < 200_000, f"RSS grew by {growth_kb} KiB (baseline {rss_start} KiB)"


@pytest.mark.heavy
@pytest.mark.asyncio
async def test_heavy_100_concurrent_multi_journey(engine: InMemoryEngine) -> None:
    """100 concurrent jobs spread across 10 journeys."""

    journeys = await asyncio.gather(*[
        engine.create_journey(JourneyCreate(
            name=f"H{i}",
            stages=[Stage(id="stg", name="S", order=1, steps=[
                Step(id="s1", name="S1", order=1, type="tool", tool="sleep",
                     input={"seconds": 0.05})
            ])],
        ))
        for i in range(10)
    ])

    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg"))
        for j in journeys for _ in range(10)
    ])
    await asyncio.gather(*[
        wait_for_terminal(engine, jb.journey_id, jb.id, timeout=60.0)
        for jb in jobs
    ])

    for j in journeys:
        refreshed = await engine.get_journey(j.id)
        assert refreshed is not None
        assert refreshed.jobs_total == 10
        assert refreshed.jobs_done == 10
