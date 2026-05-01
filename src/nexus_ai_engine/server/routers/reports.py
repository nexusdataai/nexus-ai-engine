"""Reports router (list, create, aggregate report).

PORT FIDELITY CHECKLIST — do not simplify when porting.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    GET    /{journey_id}/aggregate-report            lines 1457-1481  (aggregate_report)
    GET    /{journey_id}/jobs/{job_id}/reports       lines 1482-1531  (list_reports)
    POST   /{journey_id}/jobs/{job_id}/reports       lines 1532-1583  (create_report)

Routes activate in phase 6 of the extraction plan; until then they return 501.

See docs/ROUTE_PARITY.md for the full rules.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(route: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{route} is not yet activated in nexus-ai-engine. Ports land in phase 6.",
    )


@router.get("/{journey_id}/aggregate-report")
async def aggregate_report(journey_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/aggregate-report")


@router.get("/{journey_id}/jobs/{job_id}/reports")
async def list_job_reports(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/reports")


@router.post("/{journey_id}/jobs/{job_id}/reports")
async def create_job_report(journey_id: str, job_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /{journey_id}/jobs/{job_id}/reports")
