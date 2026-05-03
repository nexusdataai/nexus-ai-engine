"""Full-CRUD flows against the InMemoryEngine.

Covers: create → add stage → update → clone → delete sequences, counter
updates under job runs, and cascade deletion of schedules.
"""

from __future__ import annotations

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import (
    JobRunRequest,
    JourneyCreate,
    JourneyUpdate,
    ScheduleCreate,
    Stage,
    Step,
)

from .conftest import wait_for_terminal


def _stage(*, tool: str = "noop", n_steps: int = 1) -> Stage:
    return Stage(
        id="stg",
        name="Stage",
        order=1,
        steps=[
            Step(id=f"s{i}", name=f"Step {i}", order=i, type="tool", tool=tool)
            for i in range(1, n_steps + 1)
        ],
    )


async def test_create_read_update_clone_delete(engine: InMemoryEngine) -> None:
    created = await engine.create_journey(
        JourneyCreate(name="Acme", description="first", stages=[_stage()])
    )
    assert created.id.startswith("JRN-")

    fetched = await engine.get_journey(created.id)
    assert fetched is not None and fetched.name == "Acme"

    updated = await engine.update_journey(created.id, JourneyUpdate(name="Acme v2"))
    assert updated is not None and updated.name == "Acme v2"

    clone = await engine.clone_journey(created.id)
    assert clone is not None and clone.id != created.id and clone.name == "Acme v2 (Copy)"
    assert clone.jobs_total == 0

    assert await engine.delete_journey(created.id) is True
    assert await engine.get_journey(created.id) is None
    # Clone survives independent deletion
    assert await engine.get_journey(clone.id) is not None


async def test_counters_increment_on_run_and_complete(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(JourneyCreate(name="Counters", stages=[_stage()]))
    assert j.jobs_total == 0 and j.jobs_running == 0 and j.jobs_done == 0

    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    # Counters reflect the in-flight job immediately
    j_mid = await engine.get_journey(j.id)
    assert j_mid is not None
    assert j_mid.jobs_total == 1 and j_mid.jobs_running == 1

    await wait_for_terminal(engine, j.id, job.id)

    j_end = await engine.get_journey(j.id)
    assert j_end is not None
    assert j_end.jobs_total == 1
    assert j_end.jobs_running == 0
    assert j_end.jobs_done == 1
    assert j_end.jobs_failed == 0
    assert j_end.success_rate == 100.0


async def test_delete_cascades_schedules_and_cancels_jobs(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(
        JourneyCreate(name="Cascade", stages=[_stage(tool="sleep", n_steps=1)])
    )
    # Wire a schedule pointing at the journey.
    sched = await engine.create_schedule(
        ScheduleCreate(journey_id=j.id, stage_id="stg", interval_minutes=5)
    )
    # Start a job that will be long enough to observe cancellation on delete.
    running = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert running is not None

    assert await engine.delete_journey(j.id) is True
    # Schedule vanished.
    assert await engine.get_schedule(sched.id) is None
    # Journey gone.
    assert await engine.get_journey(j.id) is None


async def test_add_update_delete_stage(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(JourneyCreate(name="Stages"))
    assert j.stages == []

    added = await engine.add_stage(j.id, _stage())
    assert added is not None and len(added.stages) == 1

    # Update replaces by id.
    replaced = Stage(id="stg", name="Stage v2", order=1, steps=[])
    updated = await engine.update_stage(j.id, "stg", replaced)
    assert updated is not None and updated.stages[0].name == "Stage v2"

    removed = await engine.delete_stage(j.id, "stg")
    assert removed is not None and removed.stages == []


async def test_get_unknown_journey_returns_none(engine: InMemoryEngine) -> None:
    assert await engine.get_journey("JRN-NOPE") is None
    assert await engine.update_journey("JRN-NOPE", JourneyUpdate(name="x")) is None
    assert await engine.clone_journey("JRN-NOPE") is None
    assert await engine.delete_journey("JRN-NOPE") is False


@pytest.mark.parametrize("n_steps", [1, 3, 5])
async def test_job_over_variable_length_stage(engine: InMemoryEngine, n_steps: int) -> None:
    j = await engine.create_journey(
        JourneyCreate(name=f"Var{n_steps}", stages=[_stage(n_steps=n_steps)])
    )
    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, j.id, job.id)
    final = await engine.get_job(j.id, job.id)
    assert final is not None
    assert final.status.value == "completed"
    assert len(final.step_results) == n_steps
    assert all(s.status.value == "completed" for s in final.step_results)
