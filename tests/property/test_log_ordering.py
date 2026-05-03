"""Within a single job, log timestamps are monotonically non-decreasing."""

from __future__ import annotations

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step
from tests.fixtures.steps import register_all


@given(
    n_steps=st.integers(min_value=1, max_value=3),
    per_step=st.integers(min_value=1, max_value=12),
)
async def test_log_timestamps_monotonic(n_steps: int, per_step: int) -> None:
    engine = InMemoryEngine()
    register_all(engine)
    j = await engine.create_journey(
        JourneyCreate(
            name="logs",
            stages=[
                Stage(
                    id="stg", name="S", order=1,
                    steps=[
                        Step(
                            id=f"s{i}", name=f"S{i}", order=i,
                            type="tool", tool="count_to",
                            input={"n": per_step, "delay_seconds": 0},
                        )
                        for i in range(1, n_steps + 1)
                    ],
                )
            ],
        )
    )
    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    for _ in range(400):
        if (await engine.get_job(j.id, job.id)).status.value != "running":
            break
        await asyncio.sleep(0.01)

    logs = await engine.get_job_logs(j.id, job.id)
    ts = [e.timestamp for e in logs]
    assert ts == sorted(ts), "log timestamps must be non-decreasing within a job"
    # step boundaries appear in file-definition order
    step_starts = [
        e.step_id for e in logs if e.message.startswith("Starting step")
    ]
    expected = [f"s{i}" for i in range(1, n_steps + 1)]
    assert step_starts == expected
