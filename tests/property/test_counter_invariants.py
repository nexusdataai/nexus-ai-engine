"""Journey counter-math invariants under randomized job outcomes."""

from __future__ import annotations

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step
from tests.fixtures.steps import register_all


def _stage_for(outcome: str) -> Stage:
    if outcome == "ok":
        step = Step(id="s1", name="S1", order=1, type="tool", tool="noop")
    else:  # outcome == "fail"
        step = Step(
            id="s1", name="S1", order=1, type="tool", tool="fail_after",
            input={"n_ticks": 1, "message": "x"},
        )
    return Stage(id="stg", name="S", order=1, steps=[step])


@given(
    outcomes=st.lists(
        st.sampled_from(["ok", "fail"]), min_size=0, max_size=8
    ),
)
async def test_total_equals_done_plus_failed(outcomes: list[str]) -> None:
    engine = InMemoryEngine()
    register_all(engine)

    # Add a stage that matches the first outcome; switch as we run.
    # For simplicity each run creates a fresh journey so stages align
    # with their intended outcome.
    for outcome in outcomes:
        stg = _stage_for(outcome)
        tmp = await engine.create_journey(
            JourneyCreate(name=f"j-{outcome}", stages=[stg])
        )
        job = await engine.run_job(tmp.id, JobRunRequest(stage_id="stg"))
        assert job is not None
        for _ in range(400):
            if (await engine.get_job(tmp.id, job.id)).status.value != "running":
                break
            await asyncio.sleep(0.005)

        final = await engine.get_journey(tmp.id)
        assert final is not None
        # Invariants on each journey independently:
        assert final.jobs_total == 1
        assert final.jobs_running == 0
        assert final.jobs_done + final.jobs_failed == 1
        assert 0.0 <= final.success_rate <= 100.0
