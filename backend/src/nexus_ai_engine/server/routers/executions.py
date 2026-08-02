"""Executions API — in-process ExecutionManager (docs/spec/060, rc1)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...contracts.execution_state import ExecutionState, ExecutionStatus
from ...execution import InMemoryEngine
from ...executor.manager import SubmitExecutionRequest
from ..routers._deps import get_engine

router = APIRouter()


class SubmitExecutionBody(BaseModel):
    journey_id: str
    journey_version: int | None = None
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
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    if body.dry_run or body.mode == "dry_run":
        raise HTTPException(status_code=501, detail="dry_run not implemented in rc1")

    journey = engine.dsl_store.get(body.journey_id, body.journey_version)
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Journey {body.journey_id} not found")

    state = engine.execution_manager.submit(
        SubmitExecutionRequest(
            journey=journey,
            tenant_id=uuid4(),
            submitted_by=body.labels.get("triggered_by", "api"),
            trace_id=f"exec:{body.journey_id}",
        )
    )
    asyncio.create_task(engine.run_execution_to_completion(state.execution_id))
    return {
        "execution_id": str(state.execution_id),
        "status": state.status.value.upper(),
        "journey_id": body.journey_id,
        "links": _links(state.execution_id),
    }


@router.get("/")
async def list_executions(
    journey_id: str | None = None,
    status_filter: str | None = None,
    engine: InMemoryEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    items = engine.execution_manager.list_executions()
    if journey_id:
        items = [s for s in items if s.journey_id == journey_id]
    if status_filter:
        items = [s for s in items if s.status.value == status_filter.lower()]
    return [
        {
            "execution_id": str(s.execution_id),
            "journey_id": s.journey_id,
            "status": s.status.value,
            "revision": s.revision,
        }
        for s in items
    ]


@router.get("/{execution_id}")
async def get_execution(
    execution_id: UUID,
    engine: InMemoryEngine = Depends(get_engine),
) -> ExecutionState:
    state = engine.execution_manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return state


@router.get("/{execution_id}/nodes")
async def list_nodes(
    execution_id: UUID,
    engine: InMemoryEngine = Depends(get_engine),
) -> list[dict[str, Any]]:
    state = engine.execution_manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return [ns.model_dump(mode="json") for ns in state.nodes.values()]


@router.get("/{execution_id}/graph")
async def get_graph(
    execution_id: UUID,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    graph = engine.execution_manager.get_graph(execution_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return graph.model_dump(mode="json")


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: UUID,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    state = engine.execution_manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if state.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Execution already terminal: {state.status.value}")
    updated = engine.execution_manager.cancel(execution_id)
    return {"execution_id": str(execution_id), "status": updated.status.value}


@router.post("/{execution_id}/pause")
async def pause_execution(
    execution_id: UUID,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, str]:
    state = engine.execution_manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    updated = engine.execution_manager.pause(execution_id)
    return {"execution_id": str(execution_id), "status": updated.status.value}


@router.post("/{execution_id}/resume")
async def resume_execution(
    execution_id: UUID,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, str]:
    state = engine.execution_manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    updated = engine.execution_manager.resume(execution_id)
    asyncio.create_task(engine.run_execution_to_completion(execution_id))
    return {"execution_id": str(execution_id), "status": updated.status.value}
