"""Executions API — DynamoDB-backed runtime + in-memory fallback (spec 060)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...contracts.execution_state import ExecutionState, ExecutionStatus
from ...executor.admission import AdmissionRejectedError
from ..routers._deps import get_dsl_store, get_engine, get_execution_runtime

router = APIRouter()


class SubmitExecutionBody(BaseModel):
    journey_id: str
    journey_version: int | None = None
    tenant_id: str | None = None
    mode: str = Field(default="full", pattern="^(full|single_stage|dry_run)$")
    stage_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False


def _links(execution_id: UUID) -> dict[str, str]:
    eid = str(execution_id)
    return {
        "self": f"/api/v1/executions/{eid}",
        "stream": f"/api/v1/executions/{eid}/stream",
        "graph": f"/api/v1/executions/{eid}/graph",
        "nodes": f"/api/v1/executions/{eid}/nodes",
    }


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def submit_execution(
    body: SubmitExecutionBody,
    runtime=Depends(get_execution_runtime),
    dsl_store=Depends(get_dsl_store),
) -> dict[str, Any]:
    if body.dry_run or body.mode == "dry_run":
        raise HTTPException(status_code=501, detail="dry_run not implemented")

    journey = dsl_store.get(body.journey_id, body.journey_version)
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Journey {body.journey_id} not found")

    tenant = UUID(body.tenant_id) if body.tenant_id else uuid4()
    try:
        state = await runtime.submit(
            journey,
            tenant_id=tenant,
            submitted_by=body.labels.get("triggered_by", "api"),
            trace_id=f"exec:{body.journey_id}",
        )
    except AdmissionRejectedError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    return {
        "execution_id": str(state.execution_id),
        "status": state.status.value.upper(),
        "journey_id": body.journey_id,
        "tenant_id": state.tenant_id,
        "links": _links(state.execution_id),
    }


@router.get("/")
async def list_executions(
    journey_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    tenant_id: str | None = None,
    runtime=Depends(get_execution_runtime),
) -> list[dict[str, Any]]:
    tid = tenant_id or ""
    items = await runtime.list_executions(tid, journey_id=journey_id, status_filter=status_filter)
    return [
        {
            "execution_id": str(s.execution_id),
            "journey_id": s.journey_id,
            "status": s.status.value,
            "revision": s.revision,
            "tenant_id": s.tenant_id,
        }
        for s in items
    ]


@router.get("/{execution_id}")
async def get_execution(
    execution_id: UUID,
    tenant_id: str | None = None,
    runtime=Depends(get_execution_runtime),
) -> ExecutionState:
    state = await runtime.get(tenant_id or "", execution_id)
    if state is None:
        state = await runtime.get("", execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return state


@router.get("/{execution_id}/nodes")
async def list_nodes(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> list[dict[str, Any]]:
    state = await runtime.get("", execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return [ns.model_dump(mode="json") for ns in state.nodes.values()]


@router.get("/{execution_id}/graph")
async def get_graph(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> dict[str, Any]:
    graph = runtime.get_graph(execution_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return graph.model_dump(mode="json")


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> StreamingResponse:
    state = await runtime.get("", execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return StreamingResponse(
        runtime.sse.subscribe(str(execution_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{execution_id}/stream/status")
async def stream_status(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> dict[str, Any]:
    return {
        "executionId": str(execution_id),
        "subscribers": runtime.sse.subscriber_count(str(execution_id)),
    }


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> dict[str, Any]:
    state = await runtime.get("", execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if state.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Execution already terminal: {state.status.value}")
    updated = await runtime.cancel(execution_id)
    return {"execution_id": str(execution_id), "status": updated.status.value}


@router.post("/{execution_id}/pause")
async def pause_execution(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> dict[str, str]:
    state = await runtime.get("", execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    updated = await runtime.pause(execution_id)
    return {"execution_id": str(execution_id), "status": updated.status.value}


@router.post("/{execution_id}/resume")
async def resume_execution(
    execution_id: UUID,
    runtime=Depends(get_execution_runtime),
) -> dict[str, str]:
    state = await runtime.get("", execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    updated = await runtime.resume(execution_id)
    return {"execution_id": str(execution_id), "status": updated.status.value}
