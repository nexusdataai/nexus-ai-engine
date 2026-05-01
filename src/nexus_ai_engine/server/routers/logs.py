"""Logs router — activated against the in-memory engine.

PORT FIDELITY CHECKLIST — do not simplify when porting the DynamoDB adapter.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    GET    /{journey_id}/jobs/{job_id}/logs           lines 1354-1456  (Dynamo live -> S3 -> service fallback)
    GET    /{journey_id}/jobs/{job_id}/logs/search    lines 1584-1632  (search_logs)
    GET    /{journey_id}/jobs/{job_id}/errors         lines 1633-1678  (error_summary)

Current status: activated against an in-memory engine. The three-tier fallback
(live DynamoDB LIVELOG# → S3 → service) becomes a single in-memory lookup
here; the tiering will return when the DDB/S3 adapter lands in phase 10.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...execution import InMemoryEngine
from ...models import LogEntry
from ._deps import get_engine

router = APIRouter()


@router.get("/{journey_id}/jobs/{job_id}/logs", response_model=list[LogEntry])
async def get_job_logs(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> list[LogEntry]:
    job = await engine.get_job(journey_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return await engine.get_job_logs(journey_id, job_id)


@router.get("/{journey_id}/jobs/{job_id}/logs/search", response_model=list[LogEntry])
async def search_job_logs(
    journey_id: str,
    job_id: str,
    q: str = "",
    engine: InMemoryEngine = Depends(get_engine),
) -> list[LogEntry]:
    job = await engine.get_job(journey_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if not q:
        return await engine.get_job_logs(journey_id, job_id)
    return await engine.search_job_logs(journey_id, job_id, q)


@router.get("/{journey_id}/jobs/{job_id}/errors", response_model=list[LogEntry])
async def job_error_summary(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> list[LogEntry]:
    job = await engine.get_job(journey_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return await engine.get_job_errors(journey_id, job_id)
