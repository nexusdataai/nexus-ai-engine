"""Jobs router (run, get, status, cancel, retry, SSE stream, WebSocket).

PORT FIDELITY CHECKLIST — do not simplify when porting.
Source: /opt/mycode/nexus/nexus-backend/src/apis/journey_api.py

    POST   /{journey_id}/jobs                          lines 866-943    (run_job)
    GET    /{journey_id}/jobs                          lines 944-1025   (list_jobs)
    GET    /{journey_id}/jobs/{job_id}                 lines 1026-1093  (get_job)
    GET    /{journey_id}/jobs/{job_id}/status          lines 1094-1230  (get_job_status, Dynamo preferred)
    POST   /{journey_id}/jobs/{job_id}/cancel          lines 1231-1283  (cancel_job)
    POST   /{journey_id}/jobs/{job_id}/retry           lines 1284-1353  (retry_job)
    WS     /{journey_id}/jobs/{job_id}/ws              lines 1679-1788  (websocket poll-updates)
    GET    /{journey_id}/jobs/{job_id}/stream          lines 1789-1845  (SSE job stream)
    GET    /{journey_id}/jobs/{job_id}/stream/status   lines 1846-1864  (SSE subscriber stats)

Every fix, optimization, retry, caching, decimal conversion, error path, and
edge case in the source must be preserved verbatim during the phase port.
Routes activate in phase 7 of the extraction plan; until then they return 501.

See docs/ROUTE_PARITY.md for the full rules.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, status

router = APIRouter()


def _not_implemented(route: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{route} is not yet activated in nexus-ai-engine. Ports land in phase 7.",
    )


@router.post("/{journey_id}/jobs")
async def run_job(journey_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /{journey_id}/jobs")


@router.get("/{journey_id}/jobs")
async def list_jobs(journey_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs")


@router.get("/{journey_id}/jobs/{job_id}")
async def get_job(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}")


@router.get("/{journey_id}/jobs/{job_id}/status")
async def get_job_status(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/status")


@router.post("/{journey_id}/jobs/{job_id}/cancel")
async def cancel_job(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("POST /{journey_id}/jobs/{job_id}/cancel")


@router.post("/{journey_id}/jobs/{job_id}/retry")
async def retry_job(journey_id: str, job_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /{journey_id}/jobs/{job_id}/retry")


@router.get("/{journey_id}/jobs/{job_id}/stream")
async def stream_job(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/stream")


@router.get("/{journey_id}/jobs/{job_id}/stream/status")
async def stream_status(journey_id: str, job_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/jobs/{job_id}/stream/status")


@router.websocket("/{journey_id}/jobs/{job_id}/ws")
async def job_websocket(websocket: WebSocket, journey_id: str, job_id: str) -> None:
    await websocket.close(code=1011, reason="WebSocket endpoint not yet activated (phase 7)")
