"""Journeys router (CRUD, stages, batch, clone, metrics).

PORT FIDELITY CHECKLIST — do not simplify when porting.
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

Every fix, optimization, retry, caching, decimal conversion, error path, and
edge case in the source must be preserved verbatim during the phase port.
Routes activate in phase 9 of the extraction plan; until then they return 501.

See docs/ROUTE_PARITY.md for the full rules.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(route: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{route} is not yet activated in nexus-ai-engine. Ports land in phase 9.",
    )


@router.post("/")
async def create_journey(payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /")


@router.get("/")
async def list_journeys() -> dict:
    raise _not_implemented("GET /")


@router.get("/{journey_id}")
async def get_journey(journey_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}")


@router.get("/{journey_id}/status")
async def get_journey_status(journey_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/status")


@router.delete("/{journey_id}")
async def delete_journey(journey_id: str) -> dict:
    raise _not_implemented("DELETE /{journey_id}")


@router.post("/batch")
async def batch_op(payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /batch")


@router.post("/{journey_id}/execute")
async def execute_journey(journey_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /{journey_id}/execute")


@router.get("/{journey_id}/metrics")
async def journey_metrics(journey_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/metrics")


@router.post("/{journey_id}/clone")
async def clone_journey(journey_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /{journey_id}/clone")


@router.get("/{journey_id}/stages")
async def list_stages(journey_id: str) -> dict:
    raise _not_implemented("GET /{journey_id}/stages")


@router.post("/{journey_id}/stages")
async def add_stage(journey_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("POST /{journey_id}/stages")


@router.put("/{journey_id}/stages/{stage_id}")
async def update_stage(journey_id: str, stage_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("PUT /{journey_id}/stages/{stage_id}")


@router.delete("/{journey_id}/stages/{stage_id}")
async def delete_stage(journey_id: str, stage_id: str) -> dict:
    raise _not_implemented("DELETE /{journey_id}/stages/{stage_id}")
