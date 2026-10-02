"""Operations Runbooks REST API — stale jobs and crash analyzer."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from ...services.runbooks_service import get_runbooks_service

router = APIRouter(prefix="/runbooks", tags=["runbooks"])


class CancelStaleRequest(BaseModel):
    skip_unverified_long: bool = True
    reason: str = "Cancelled via Operations runbook UI"


class CancelJobRequest(BaseModel):
    job_id: str
    journey_id: str
    stage_id: str = ""
    current_step: str = ""
    age_min: float = 0
    confidence: str = "STALE"
    pk: str
    sk: str


@router.get("/stale-jobs")
async def list_stale_jobs(
    threshold_min: Optional[int] = Query(None, ge=1, le=1440),
) -> Dict[str, Any]:
    try:
        return get_runbooks_service().list_stale_jobs(threshold_min=threshold_min)
    except Exception as exc:
        logger.error("Stale jobs list failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to scan stale jobs") from exc


@router.post("/stale-jobs/cancel-all")
async def cancel_all_stale_jobs(body: CancelStaleRequest) -> Dict[str, Any]:
    try:
        return get_runbooks_service().cancel_stale_jobs(
            skip_unverified_long=body.skip_unverified_long,
            reason=body.reason,
        )
    except Exception as exc:
        logger.error("Cancel stale jobs failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to cancel stale jobs") from exc


@router.post("/stale-jobs/cancel-one")
async def cancel_one_stale_job(body: CancelJobRequest) -> Dict[str, Any]:
    try:
        return get_runbooks_service().cancel_job(body.model_dump())
    except Exception as exc:
        logger.error("Cancel job failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to cancel job") from exc


@router.get("/crashes")
async def list_crashes(
    component: str = Query("", description="Filter pod name substring, e.g. backend"),
    log_tail: int = Query(100, ge=20, le=500),
) -> Dict[str, Any]:
    try:
        return get_runbooks_service().list_crashed_pods(component=component, log_tail=log_tail)
    except Exception as exc:
        logger.error("Crash analyzer failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to analyze pod crashes") from exc
