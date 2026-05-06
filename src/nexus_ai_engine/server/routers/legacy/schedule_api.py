"""
Batch Schedule REST API
Endpoints for managing periodic job schedules for journey stages.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger

from ....services.scheduler_service import SchedulerService

router = APIRouter()


class CreateScheduleRequest(BaseModel):
    journey_id: str
    stage_id: str
    interval_minutes: int = Field(..., ge=1, le=1440)
    enabled: bool = True
    timezone: str = 'UTC'


class UpdateScheduleRequest(BaseModel):
    interval_minutes: Optional[int] = Field(None, ge=1, le=1440)
    enabled: Optional[bool] = None
    timezone: Optional[str] = None


def _get_service() -> SchedulerService:
    return SchedulerService.get_instance()


@router.post("/")
async def create_schedule(req: CreateScheduleRequest):
    svc = _get_service()
    schedule = svc.create_schedule(
        journey_id=req.journey_id,
        stage_id=req.stage_id,
        interval_minutes=req.interval_minutes,
        enabled=req.enabled,
        timezone_str=req.timezone,
        created_by='ui',
    )
    return {"success": True, "data": schedule}


@router.get("/")
async def list_schedules(journey_id: Optional[str] = Query(None)):
    svc = _get_service()
    schedules = svc.list_schedules(journey_id=journey_id)
    return {"success": True, "data": schedules, "total": len(schedules)}


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: str):
    svc = _get_service()
    schedule = svc.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"success": True, "data": schedule}


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: str, req: UpdateScheduleRequest):
    svc = _get_service()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    schedule = svc.update_schedule(schedule_id, updates)
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"success": True, "data": schedule}


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    svc = _get_service()
    deleted = svc.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"success": True, "message": f"Schedule {schedule_id} deleted"}


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: str):
    svc = _get_service()
    schedule = svc.toggle_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"success": True, "data": schedule}


@router.post("/{schedule_id}/reset")
async def reset_schedule(schedule_id: str):
    svc = _get_service()
    schedule = svc.reset_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"success": True, "data": schedule}


@router.post("/{schedule_id}/run-now")
async def run_schedule_now(schedule_id: str):
    svc = _get_service()
    schedule = await svc.run_now(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"success": True, "data": schedule}
