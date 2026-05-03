"""Concurrent jobs across multiple journeys; verify per-journey aggregates."""

from __future__ import annotations

import asyncio

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


@pytest.mark.asyncio
async def test_five_by_ten(engine: InMemoryEngine) -> None:
    """5 journeys × 10 jobs each = 50 concurrent jobs."""

    journeys = await asyncio.gather(*[
        engine.create_journey(JourneyCreate(
            name=f"J{i}",
            stages=[Stage(id="stg", name="S", order=1, steps=[
                Step(id="s1", name="S1", order=1, type="tool", tool="noop")
            ])],
        ))
        for i in range(5)
    ])

    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg"))
        for j in journeys
        for _ in range(10)
    ])
    assert all(jb is not None for jb in jobs)

    await asyncio.gather(*[
        wait_for_terminal(engine, jb.journey_id, jb.id, timeout=15.0)
        for jb in jobs
    ])

    for j in journeys:
        refreshed = await engine.get_journey(j.id)
        assert refreshed is not None
        assert refreshed.jobs_total == 10
        assert refreshed.jobs_done == 10
        assert refreshed.jobs_running == 0
        assert refreshed.jobs_failed == 0
