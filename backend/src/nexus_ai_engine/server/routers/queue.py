"""Redis job queue observability API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ...services.job_queue_service import (
    get_queue_snapshot,
    get_queue_timeline,
    is_queue_mode,
    list_queue_jobs,
    redis_available,
)

router = APIRouter(prefix="/queue", tags=["queue"])

QueueState = Literal["waiting", "claimed", "running", "pending", "all"]


def _require_queue_mode() -> None:
    if not is_queue_mode():
        raise HTTPException(
            status_code=503,
            detail="Queue API requires JOB_EXECUTION_MODE=queue",
        )
    if not redis_available():
        raise HTTPException(
            status_code=503,
            detail="Queue API requires REDIS_URL but Redis is unavailable",
        )


@router.get("/summary")
async def queue_summary() -> dict[str, Any]:
    _require_queue_mode()
    return get_queue_snapshot()


@router.get("/jobs")
async def queue_jobs(
    state: QueueState = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _require_queue_mode()
    jobs = list_queue_jobs(state=state, limit=limit)
    return {"jobs": jobs, "count": len(jobs), "state": state}


@router.get("/timeline")
async def queue_timeline(
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    _require_queue_mode()
    events = get_queue_timeline(limit=limit)
    return {"events": events, "count": len(events)}
