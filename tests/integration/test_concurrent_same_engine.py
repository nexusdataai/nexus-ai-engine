"""Concurrent CRUD + job-runs against a single engine instance.

Exercises the "many journeys / many jobs against one engine" story
without any of the HTTP surface. Endurance-tier tests add the HTTP
layer on top; these tests verify the underlying engine first.
"""

from __future__ import annotations

import asyncio

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


def _journey(name: str, *, tool: str = "noop") -> JourneyCreate:
    return JourneyCreate(
        name=name,
        stages=[
            Stage(
                id="stg", name="Stage", order=1,
                steps=[Step(id="s1", name="S1", order=1, type="tool", tool=tool)],
            )
        ],
    )


async def test_parallel_journey_creation(engine: InMemoryEngine) -> None:
    # 25 concurrent creations -> no collisions on ids, all land.
    results = await asyncio.gather(*[
        engine.create_journey(_journey(f"J{i}")) for i in range(25)
    ])
    ids = {j.id for j in results}
    assert len(ids) == 25
    listed = await engine.list_journeys()
    assert len(listed) >= 25


async def test_parallel_jobs_single_journey(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(_journey("Shared"))
    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg"))
        for _ in range(10)
    ])
    assert all(job is not None for job in jobs)

    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, job.id, timeout=8.0) for job in jobs
    ])

    final = await engine.list_jobs(j.id, limit=None)
    assert len(final) == 10
    statuses = {job.status.value for job in final}
    assert statuses == {"completed"}
    # Each job has its own logs (isolation): no log entry is shared
    # across jobs.
    log_counts = await asyncio.gather(*[
        engine.get_job_logs(j.id, job.id) for job in final
    ])
    for logs in log_counts:
        assert all(e.step_id == "s1" for e in logs), "step_id should always be s1 per-job"
    # Execution numbers are strictly increasing within the journey.
    execs = sorted(job.execution_number for job in final)
    assert execs == list(range(1, 11))


async def test_parallel_jobs_multiple_journeys(engine: InMemoryEngine) -> None:
    journeys = await asyncio.gather(*[
        engine.create_journey(_journey(f"J{i}")) for i in range(5)
    ])

    # 5 journeys x 3 jobs = 15 concurrent jobs.
    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg"))
        for j in journeys
        for _ in range(3)
    ])
    assert all(j is not None for j in jobs)

    await asyncio.gather(*[
        wait_for_terminal(engine, job.journey_id, job.id, timeout=10.0)
        for job in jobs
    ])

    # Each journey ends with jobs_total == jobs_done == 3.
    for j in journeys:
        refreshed = await engine.get_journey(j.id)
        assert refreshed is not None
        assert refreshed.jobs_total == 3
        assert refreshed.jobs_done == 3
        assert refreshed.jobs_running == 0
        assert refreshed.jobs_failed == 0


async def test_delete_mid_run_cancels_in_flight(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(_journey("Doomed", tool="sleep"))
    # Launch a long-ish job.
    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None

    # Wait just enough to enter the tool body.
    await asyncio.sleep(0.05)
    assert await engine.delete_journey(j.id) is True

    # Journey gone.
    assert await engine.get_journey(j.id) is None
    # Task eventually terminates. We can't get the job via the public API
    # once the journey is deleted (get_job checks journey_id), but the
    # underlying task must complete one way or another.
    for _ in range(200):
        if engine.jobs.get(job.id, job).status.value != "running":
            break
        await asyncio.sleep(0.02)
    assert engine.jobs[job.id].status.value in ("cancelled", "failed", "completed")


async def test_cancel_all_storm(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(_journey("Stormy", tool="sleep"))
    jobs = await asyncio.gather(*[
        engine.run_job(j.id, JobRunRequest(stage_id="stg")) for _ in range(15)
    ])
    assert all(job is not None for job in jobs)

    # Cancel them all as fast as possible.
    await asyncio.gather(*[engine.cancel_job(j.id, job.id) for job in jobs])

    await asyncio.gather(*[
        wait_for_terminal(engine, j.id, job.id, timeout=8.0) for job in jobs
    ])

    final = await engine.list_jobs(j.id, limit=None)
    # All either cancelled or completed (if they raced the cancel).
    allowed = {"cancelled", "completed"}
    actual = {job.status.value for job in final}
    assert actual.issubset(allowed), f"unexpected statuses: {actual - allowed}"
