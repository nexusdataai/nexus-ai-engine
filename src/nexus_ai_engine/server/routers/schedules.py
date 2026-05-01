"""Schedules router — new, not inherited from nexus-backend.

Supports the Batch Schedules panel in the embedded UI. Minimal CRUD plus
a "run now" action that creates a job via the engine's simulated executor.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...execution import InMemoryEngine
from ...models import Job, Schedule, ScheduleCreate, ScheduleUpdate
from ._deps import get_engine

router = APIRouter()


@router.get("/", response_model=list[Schedule])
async def list_schedules(
    journey_id: str | None = None, engine: InMemoryEngine = Depends(get_engine)
) -> list[Schedule]:
    return await engine.list_schedules(journey_id=journey_id)


@router.post("/", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate, engine: InMemoryEngine = Depends(get_engine)
) -> Schedule:
    # Validate the journey and stage exist before accepting
    journey = await engine.get_journey(body.journey_id)
    if not journey or not any(s.id == body.stage_id for s in journey.stages):
        raise HTTPException(
            status_code=404,
            detail=f"Journey {body.journey_id} or stage {body.stage_id} not found",
        )
    return await engine.create_schedule(body)


@router.get("/{schedule_id}", response_model=Schedule)
async def get_schedule(schedule_id: str, engine: InMemoryEngine = Depends(get_engine)) -> Schedule:
    s = await engine.get_schedule(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return s


@router.patch("/{schedule_id}", response_model=Schedule)
async def update_schedule(
    schedule_id: str, body: ScheduleUpdate, engine: InMemoryEngine = Depends(get_engine)
) -> Schedule:
    s = await engine.update_schedule(schedule_id, body)
    if not s:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return s


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> dict:
    ok = await engine.delete_schedule(schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"deleted": schedule_id}


@router.post("/{schedule_id}/run", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def run_schedule_now(
    schedule_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> Job:
    job = await engine.run_schedule_now(schedule_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found or invalid")
    return job
