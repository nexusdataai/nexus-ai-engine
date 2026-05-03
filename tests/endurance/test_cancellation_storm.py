"""Cancel a burst of in-flight jobs; none hang."""

from __future__ import annotations

import asyncio

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


@pytest.mark.asyncio
async def test_storm_twenty_cancels(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(JourneyCreate(
        name="storm",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(
                id="long", name="long", order=1, type="tool",
                tool="cancel_checkpoint",
                input={"total_seconds": 3.0, "check_every_seconds": 0.05},
            )
        ])],
    ))

    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg")) for _ in range(20)
    ])
    assert all(jb is not None for jb in jobs)
    # Let tools actually enter their loop.
    await asyncio.sleep(0.1)

    await asyncio.gather(*[engine.cancel_job(j.id, jb.id) for jb in jobs])

    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, jb.id, timeout=10.0) for jb in jobs
    ])

    final = await engine.list_jobs(j.id, limit=None)
    statuses = {jb.status.value for jb in final}
    # All either cancelled or completed (race for early cancel).
    assert statuses.issubset({"cancelled", "completed"}), statuses
