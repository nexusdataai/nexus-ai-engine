"""Logs router (step logs, log search, error summary).

PORT FIDELITY CHECKLIST — do not simplify when porting.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    GET    /{journey_id}/jobs/{job_id}/logs           lines 1354-1456  (Dynamo live -> S3 -> service fallback)
    GET    /{journey_id}/jobs/{job_id}/logs/search    lines 1584-1632  (search_logs)
    GET    /{journey_id}/jobs/{job_id}/errors         lines 1633-1678  (error_summary)

The logs path has multi-tier fallback behavior (live Dynamo LIVELOG#, then S3,
then LogsAndReportsService). Preserve all three tiers and the try/except
ordering. Routes activate in phase 6.

See docs/ROUTE_PARITY.md for the full rules.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(route: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{route} is not yet activated in nexus-ai-engine. Ports land in phase 6.",
    )


@router.get("/{journey_id}/jobs/{job_id}/logs")
async def get_job_logs(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/logs")


@router.get("/{journey_id}/jobs/{job_id}/logs/search")
async def search_job_logs(journey_id: str, job_id: str, q: str = "") -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/logs/search")


@router.get("/{journey_id}/jobs/{job_id}/errors")
async def job_error_summary(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/errors")
