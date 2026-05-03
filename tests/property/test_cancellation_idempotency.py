"""Cancellation is idempotent and terminal states are absorbing."""

from __future__ import annotations

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JobStatus, JourneyCreate, Stage, Step
from tests.fixtures.steps import register_all


@given(n_cancels=st.integers(min_value=1, max_value=5))
async def test_cancel_n_times_same_terminal(n_cancels: int) -> None:
    engine = InMemoryEngine()
    register_all(engine)
    j = await engine.create_journey(
        JourneyCreate(
            name="cancels",
            stages=[
                Stage(
                    id="stg", name="S", order=1,
                    steps=[
                        Step(
                            id="long", name="long", order=1, type="tool",
                            tool="cancel_checkpoint",
                            input={"total_seconds": 1.0, "check_every_seconds": 0.02},
                        )
                    ],
                )
            ],
        )
    )
    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    await asyncio.sleep(0.03)

    # Fire cancel N times in parallel.
    await asyncio.gather(*[engine.cancel_job(j.id, job.id) for _ in range(n_cancels)])

    # Wait for terminal.
    for _ in range(300):
        if (await engine.get_job(j.id, job.id)).status.value != "running":
            break
        await asyncio.sleep(0.01)

    final = (await engine.get_job(j.id, job.id)).status
    assert final in {JobStatus.cancelled, JobStatus.completed}, final

    # Cancelling after terminal returns the job unchanged.
    post = await engine.cancel_job(j.id, job.id)
    assert post is not None
    assert post.status == final
