"""Journeys router — activated against the in-memory engine.

PORT FIDELITY CHECKLIST — do not simplify when porting the DynamoDB adapter.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    POST   /                                         lines 156-202   (create_journey)
    GET    /{journey_id}                             lines 203-252   (get_journey)
    GET    /{journey_id}/status                      lines 253-306   (get_journey_status)
    GET    /                                         lines 307-382   (list_journeys)
    DELETE /{journey_id}                             lines 383-417   (delete_journey)
    POST   /batch                                    lines 418-487   (batch_op)
    POST   /{journey_id}/execute                     lines 488-538   (execute_journey stub)
    GET    /{journey_id}/metrics                     lines 539-588   (journey_metrics)
    POST   /{journey_id}/clone                       lines 589-643   (clone_journey)
    GET    /{journey_id}/stages                      lines 644-697   (list_stages)
    POST   /{journey_id}/stages                      lines 698-765   (add_stage)
    PUT    /{journey_id}/stages/{stage_id}           lines 766-827   (update_stage)
    DELETE /{journey_id}/stages/{stage_id}           lines 828-865   (delete_stage)

Current status: activated against an in-memory engine to support the embedded
UI and e2e tests. Swapping the backing repository to DynamoDB in phase 10
changes the service injection, not the handler bodies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ...execution import InMemoryEngine
from ...models import Journey, JourneyCreate, JourneyUpdate, Stage
from ._deps import get_engine

router = APIRouter()


@router.post("/", response_model=Journey, status_code=status.HTTP_201_CREATED)
async def create_journey(body: JourneyCreate, engine: InMemoryEngine = Depends(get_engine)) -> Journey:
    return await engine.create_journey(body)


@router.get("/", response_model=list[Journey])
async def list_journeys(
    q: str | None = None,
    status_filter: str | None = None,
    capability: str | None = None,
    limit: int | None = None,
    engine: InMemoryEngine = Depends(get_engine),
) -> list[Journey]:
    return await engine.list_journeys(query=q, status=status_filter, capability=capability, limit=limit)


@router.get("/{journey_id}", response_model=Journey)
async def get_journey(journey_id: str, engine: InMemoryEngine = Depends(get_engine)) -> Journey:
    j = await engine.get_journey(journey_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return j


@router.get("/{journey_id}/status")
async def get_journey_status(journey_id: str, engine: InMemoryEngine = Depends(get_engine)) -> dict[str, Any]:
    j = await engine.get_journey(journey_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return {
        "journeyId": j.id,
        "status": j.status.value,
        "jobsTotal": j.jobs_total,
        "jobsDone": j.jobs_done,
        "jobsRunning": j.jobs_running,
        "jobsFailed": j.jobs_failed,
        "successRate": j.success_rate,
        "avgDurationSeconds": j.avg_duration_seconds,
        "updatedAt": j.updated_at.isoformat(),
    }


@router.get("/{journey_id}/metrics")
async def journey_metrics(journey_id: str, engine: InMemoryEngine = Depends(get_engine)) -> dict[str, Any]:
    j = await engine.get_journey(journey_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return {
        "journeyId": j.id,
        "name": j.name,
        "jobsTotal": j.jobs_total,
        "jobsDone": j.jobs_done,
        "jobsFailed": j.jobs_failed,
        "jobsRunning": j.jobs_running,
        "successRate": j.success_rate,
        "avgDurationSeconds": j.avg_duration_seconds,
    }


@router.delete("/{journey_id}")
async def delete_journey(journey_id: str, engine: InMemoryEngine = Depends(get_engine)) -> dict[str, Any]:
    ok = await engine.delete_journey(journey_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return {"deleted": journey_id}


@router.patch("/{journey_id}", response_model=Journey)
async def update_journey(
    journey_id: str, body: JourneyUpdate, engine: InMemoryEngine = Depends(get_engine)
) -> Journey:
    j = await engine.update_journey(journey_id, body)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return j


@router.post("/{journey_id}/clone", response_model=Journey, status_code=status.HTTP_201_CREATED)
async def clone_journey(
    journey_id: str, body: dict[str, Any] | None = None, engine: InMemoryEngine = Depends(get_engine)
) -> Journey:
    new_name = (body or {}).get("name")
    clone = await engine.clone_journey(journey_id, new_name=new_name)
    if not clone:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return clone


@router.get("/{journey_id}/stages", response_model=list[Stage])
async def list_stages(journey_id: str, engine: InMemoryEngine = Depends(get_engine)) -> list[Stage]:
    j = await engine.get_journey(journey_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return list(j.stages)


@router.post("/{journey_id}/stages", response_model=Journey, status_code=status.HTTP_201_CREATED)
async def add_stage(
    journey_id: str, stage: Stage, engine: InMemoryEngine = Depends(get_engine)
) -> Journey:
    j = await engine.add_stage(journey_id, stage)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return j


@router.put("/{journey_id}/stages/{stage_id}", response_model=Journey)
async def update_stage(
    journey_id: str, stage_id: str, stage: Stage, engine: InMemoryEngine = Depends(get_engine)
) -> Journey:
    j = await engine.update_stage(journey_id, stage_id, stage)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} or stage {stage_id} not found")
    return j


@router.delete("/{journey_id}/stages/{stage_id}", response_model=Journey)
async def delete_stage(
    journey_id: str, stage_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> Journey:
    j = await engine.delete_stage(journey_id, stage_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} or stage {stage_id} not found")
    return j
