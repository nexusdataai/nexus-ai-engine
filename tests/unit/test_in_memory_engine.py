"""Unit tests for InMemoryEngine."""

from __future__ import annotations

import asyncio

import pytest

from nexus_ai_engine.execution import InMemoryEngine, seed
from nexus_ai_engine.models import (
    JobRunRequest,
    JobStatus,
    JourneyCreate,
    PromptUpdate,
    ScheduleCreate,
    ScheduleUpdate,
    Stage,
    Step,
)


@pytest.fixture
def fresh_engine() -> InMemoryEngine:
    return InMemoryEngine()


@pytest.fixture
def seeded_engine() -> InMemoryEngine:
    engine = InMemoryEngine()
    seed(engine)
    return engine


async def test_seed_creates_five_journeys(seeded_engine: InMemoryEngine) -> None:
    journeys = await seeded_engine.list_journeys()
    assert len(journeys) == 5
    kinds = {j.kind for j in journeys}
    assert kinds == {
        "order_to_cash",
        "call_processing",
        "demand_forecasting",
        "inventory_optimization",
        "supply_chain_risk",
    }


async def test_seed_creates_schedules_and_prompts(seeded_engine: InMemoryEngine) -> None:
    schedules = await seeded_engine.list_schedules()
    assert len(schedules) == 3
    prompts = await seeded_engine.list_prompts()
    assert len(prompts) >= 4
    assert any(p.is_default for p in prompts)


async def test_create_and_delete_journey(fresh_engine: InMemoryEngine) -> None:
    j = await fresh_engine.create_journey(JourneyCreate(name="Demo", capability="demo"))
    assert j.name == "Demo"
    assert j.id in fresh_engine.journeys
    assert await fresh_engine.delete_journey(j.id) is True
    assert j.id not in fresh_engine.journeys


async def test_run_job_reaches_terminal_status(seeded_engine: InMemoryEngine) -> None:
    journey = next(iter(seeded_engine.journeys.values()))
    stage = journey.stages[0]

    job = await seeded_engine.run_job(
        journey.id, JobRunRequest(stage_id=stage.id, reason="retry test")
    )
    assert job is not None
    assert job.status == JobStatus.running

    # Wait for simulated run to finish (up to 30s; should take well under)
    for _ in range(300):
        fresh = await seeded_engine.get_job(journey.id, job.id)
        if fresh and fresh.status != JobStatus.running:
            assert fresh.status in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled)
            assert fresh.duration_seconds is not None
            return
        await asyncio.sleep(0.1)
    raise AssertionError("Simulated job did not reach a terminal state in time")


async def test_cancel_job(seeded_engine: InMemoryEngine) -> None:
    journey = next(iter(seeded_engine.journeys.values()))
    stage = journey.stages[0]
    job = await seeded_engine.run_job(journey.id, JobRunRequest(stage_id=stage.id))
    assert job is not None

    await asyncio.sleep(0.2)
    await seeded_engine.cancel_job(journey.id, job.id)

    for _ in range(150):
        fresh = await seeded_engine.get_job(journey.id, job.id)
        if fresh and fresh.status == JobStatus.cancelled:
            return
        await asyncio.sleep(0.1)
    raise AssertionError("Job was not cancelled in time")


async def test_schedule_crud_and_run_now(seeded_engine: InMemoryEngine) -> None:
    journey = next(iter(seeded_engine.journeys.values()))
    stage = journey.stages[0]

    created = await seeded_engine.create_schedule(
        ScheduleCreate(journey_id=journey.id, stage_id=stage.id, interval_minutes=5)
    )
    assert created.enabled is True

    updated = await seeded_engine.update_schedule(created.id, ScheduleUpdate(enabled=False))
    assert updated is not None and updated.enabled is False

    job = await seeded_engine.run_schedule_now(created.id)
    assert job is not None
    assert job.journey_id == journey.id

    assert await seeded_engine.delete_schedule(created.id) is True


async def test_prompts_update_and_reset(seeded_engine: InMemoryEngine) -> None:
    prompts_before = await seeded_engine.list_prompts()
    target = prompts_before[0]
    updated = await seeded_engine.update_prompt(target.id, PromptUpdate(content="NEW", note="test"))
    assert updated is not None
    assert updated.content == "NEW"
    assert updated.version == target.version + 1
    audit = await seeded_engine.prompt_audit_log()
    assert audit and audit[0].prompt_id == target.id and audit[0].action == "updated"

    # Reset
    await seeded_engine.reset_prompts()
    restored = await seeded_engine.get_prompt(target.id)
    assert restored is not None and restored.content == target.content


async def test_aggregate_report(seeded_engine: InMemoryEngine) -> None:
    journey = next(iter(seeded_engine.journeys.values()))
    agg = await seeded_engine.aggregate_report(journey.id)
    assert agg is not None
    assert agg.total_jobs >= 0
    assert 0 <= agg.success_rate <= 100
