"""Jobs router — activated against the in-memory engine.

PORT FIDELITY CHECKLIST — do not simplify when porting the DynamoDB adapter.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    POST   /{journey_id}/jobs                          lines 866-943    (run_job)
    GET    /{journey_id}/jobs                          lines 944-1025   (list_jobs)
    GET    /{journey_id}/jobs/{job_id}                 lines 1026-1093  (get_job)
    GET    /{journey_id}/jobs/{job_id}/status          lines 1094-1230  (get_job_status)
    POST   /{journey_id}/jobs/{job_id}/cancel          lines 1231-1283  (cancel_job)
    POST   /{journey_id}/jobs/{job_id}/retry           lines 1284-1353  (retry_job)
    GET    /{journey_id}/jobs/{job_id}/stream          lines 1789-1845  (SSE job stream)
    GET    /{journey_id}/jobs/{job_id}/stream/status   lines 1846-1864  (SSE subscriber stats)

Current status: activated against an in-memory engine; the simulated executor
emits step_status / task_progress / job_complete events over the /stream
endpoint so the UI's logs drawer shows realistic live progress.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...execution import InMemoryEngine
from ...models import Job, JobRunRequest
from ._deps import get_engine

router = APIRouter()


@router.post("/{journey_id}/jobs", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def run_job(
    journey_id: str, body: JobRunRequest, engine: InMemoryEngine = Depends(get_engine)
) -> Job:
    job = await engine.run_job(journey_id, body)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Journey {journey_id} or stage {body.stage_id} not found"
        )
    return job


@router.get("/{journey_id}/jobs", response_model=list[Job])
async def list_jobs(
    journey_id: str, limit: int | None = 100, engine: InMemoryEngine = Depends(get_engine)
) -> list[Job]:
    return await engine.list_jobs(journey_id, limit=limit)


@router.get("/{journey_id}/jobs/{job_id}", response_model=Job)
async def get_job(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> Job:
    job = await engine.get_job(journey_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.get("/{journey_id}/jobs/{job_id}/status")
async def get_job_status(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> dict:
    status_obj = await engine.get_job_status(journey_id, job_id)
    if status_obj is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status_obj


@router.post("/{journey_id}/jobs/{job_id}/cancel", response_model=Job)
async def cancel_job(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> Job:
    job = await engine.cancel_job(journey_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/{journey_id}/jobs/{job_id}/retry", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> Job:
    new_job = await engine.retry_job(journey_id, job_id)
    if not new_job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return new_job


@router.get("/{journey_id}/jobs/{job_id}/stream")
async def stream_job(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> StreamingResponse:
    job = await engine.get_job(journey_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return StreamingResponse(
        engine.stream_job(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{journey_id}/jobs/{job_id}/stream/status")
async def stream_status(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> dict:
    return {"jobId": job_id, "subscribers": engine.sse.subscriber_count(job_id)}
