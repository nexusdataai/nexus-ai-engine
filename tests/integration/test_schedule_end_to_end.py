"""Schedule CRUD + run-now flow.

Verifies that creating a schedule + calling run_schedule_now spawns a
job bound to the schedule's journey/stage and updates the schedule's
last_run_at / next_run_at timestamps.
"""

from __future__ import annotations

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import (
    JourneyCreate,
    ScheduleCreate,
    ScheduleUpdate,
    Stage,
    Step,
)

from .conftest import wait_for_terminal


def _journey() -> JourneyCreate:
    return JourneyCreate(
        name="scheduled",
        stages=[
            Stage(
                id="stg", name="Stage", order=1,
                steps=[Step(id="s1", name="S1", order=1, type="tool", tool="noop")],
            )
        ],
    )


async def test_create_list_update_delete_schedule(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(_journey())

    created = await engine.create_schedule(
        ScheduleCreate(journey_id=j.id, stage_id="stg", interval_minutes=10)
    )
    assert created.id.startswith("SCH-")
    assert created.enabled is True
    assert created.next_run_at is not None

    listed = await engine.list_schedules(journey_id=j.id)
    assert len(listed) == 1 and listed[0].id == created.id

    # Disable it -> next_run_at should remain populated but last_status unchanged.
    disabled = await engine.update_schedule(
        created.id, ScheduleUpdate(enabled=False)
    )
    assert disabled is not None and disabled.enabled is False

    # Re-enable -> next_run_at populated from `updated_at + interval`.
    re_enabled = await engine.update_schedule(
        created.id, ScheduleUpdate(enabled=True)
    )
    assert re_enabled is not None and re_enabled.enabled is True
    assert re_enabled.next_run_at is not None

    assert await engine.delete_schedule(created.id) is True
    assert await engine.get_schedule(created.id) is None


async def test_run_now_spawns_bound_job(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(_journey())
    s = await engine.create_schedule(
        ScheduleCreate(journey_id=j.id, stage_id="stg", interval_minutes=15)
    )

    job = await engine.run_schedule_now(s.id)
    assert job is not None
    assert job.journey_id == j.id
    assert job.stage_id == "stg"
    assert job.triggered_by == "schedule"

    await wait_for_terminal(engine, j.id, job.id)

    # Schedule bookkeeping updated after run_now
    refreshed = await engine.get_schedule(s.id)
    assert refreshed is not None
    assert refreshed.last_run_at is not None
    assert refreshed.next_run_at is not None


async def test_run_schedule_now_unknown_returns_none(engine: InMemoryEngine) -> None:
    assert await engine.run_schedule_now("SCH-NOPE") is None
