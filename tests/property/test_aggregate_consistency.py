"""Aggregate-report totals must equal sum-of-jobs at any observation."""

from __future__ import annotations

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step
from tests.fixtures.steps import register_all


@given(
    ok_jobs=st.integers(min_value=0, max_value=4),
    fail_jobs=st.integers(min_value=0, max_value=3),
)
async def test_aggregate_totals_match_per_job_sum(ok_jobs: int, fail_jobs: int) -> None:
    engine = InMemoryEngine()
    register_all(engine)

    # One journey with two stages so we can target both outcomes.
    j = await engine.create_journey(
        JourneyCreate(
            name="agg",
            stages=[
                Stage(
                    id="ok", name="OK", order=1,
                    steps=[Step(id="s", name="s", order=1, type="tool", tool="noop")],
                ),
                Stage(
                    id="fail", name="Fail", order=2,
                    steps=[Step(
                        id="s", name="s", order=1, type="tool", tool="fail_after",
                        input={"n_ticks": 1, "message": "x"},
                    )],
                ),
            ],
        )
    )

    jobs = []
    for _ in range(ok_jobs):
        jobs.append(await engine.run_job(j.id, JobRunRequest(stage_id="ok")))
    for _ in range(fail_jobs):
        jobs.append(await engine.run_job(j.id, JobRunRequest(stage_id="fail")))

    # Wait for every job to reach terminal.
    async def wait(job):
        for _ in range(400):
            if (await engine.get_job(j.id, job.id)).status.value != "running":
                return
            await asyncio.sleep(0.005)

    await asyncio.gather(*[wait(job) for job in jobs if job is not None])

    report = await engine.aggregate_report(j.id)
    assert report is not None

    all_jobs = await engine.list_jobs(j.id, limit=None)
    recomputed_total = len(all_jobs)
    recomputed_completed = sum(1 for x in all_jobs if x.status.value == "completed")
    recomputed_failed = sum(1 for x in all_jobs if x.status.value == "failed")

    assert report.total_jobs == recomputed_total
    assert report.completed_jobs == recomputed_completed
    assert report.failed_jobs == recomputed_failed
    # success_rate equals completed/total*100 when total>0, else 0.
    expected_rate = (recomputed_completed / recomputed_total * 100.0) if recomputed_total else 0.0
    assert abs(report.success_rate - expected_rate) < 1e-6
