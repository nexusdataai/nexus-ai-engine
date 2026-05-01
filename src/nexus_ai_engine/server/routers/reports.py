"""Reports router — activated against the in-memory engine.

PORT FIDELITY CHECKLIST — do not simplify when porting the DynamoDB adapter.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    GET    /{journey_id}/aggregate-report            lines 1457-1481  (aggregate_report)
    GET    /{journey_id}/jobs/{job_id}/reports       lines 1482-1531  (list_reports)
    POST   /{journey_id}/jobs/{job_id}/reports       lines 1532-1583  (create_report)

Current status: activated against an in-memory engine. Reports are held in
process; S3-backed report storage lands in phase 10.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...execution import InMemoryEngine
from ...models import AggregateReport, Report, ReportCreate
from ._deps import get_engine

router = APIRouter()


@router.get("/{journey_id}/aggregate-report", response_model=AggregateReport)
async def aggregate_report(
    journey_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> AggregateReport:
    agg = await engine.aggregate_report(journey_id)
    if not agg:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return agg


@router.get("/{journey_id}/jobs/{job_id}/reports", response_model=list[Report])
async def list_job_reports(
    journey_id: str, job_id: str, engine: InMemoryEngine = Depends(get_engine)
) -> list[Report]:
    return await engine.list_job_reports(journey_id, job_id)


@router.post(
    "/{journey_id}/jobs/{job_id}/reports", response_model=Report, status_code=status.HTTP_201_CREATED
)
async def create_job_report(
    journey_id: str,
    job_id: str,
    body: ReportCreate,
    engine: InMemoryEngine = Depends(get_engine),
) -> Report:
    r = await engine.create_job_report(journey_id, job_id, body)
    if not r:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return r
