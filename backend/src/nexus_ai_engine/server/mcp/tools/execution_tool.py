"""MCP tool for execution submit/list/status (spec 060)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP

from ....contracts.journey_dsl import JourneyDefinition
from ....executor.admission import AdmissionRejectedError
from ....journeys.service import DslJourneyStore
from ....execution.runtime_service import ExecutionRuntimeService


def register_execution_tools(
    mcp: FastMCP,
    *,
    runtime: ExecutionRuntimeService | None = None,
    dsl_store: DslJourneyStore | None = None,
):
    """Register execution_tool with optional injected runtime/store."""

    @mcp.tool(
        name="execution_tool",
        description="Submit and monitor journey executions via the Executions API runtime.",
    )
    async def execution_tool(
        action: str,
        journey_id: Optional[str] = None,
        journey_version: Optional[int] = None,
        execution_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        journey_yaml: Optional[str] = None,
    ) -> dict[str, Any]:
        svc = runtime or ExecutionRuntimeService()
        store = dsl_store or DslJourneyStore()

        try:
            if action == "submit":
                if not journey_id:
                    return {"status": "error", "message": "journey_id required"}
                journey = store.get(journey_id, journey_version)
                if journey is None and journey_yaml:
                    import yaml

                    journey = JourneyDefinition.model_validate(yaml.safe_load(journey_yaml))
                    store.create(journey)
                if journey is None:
                    return {"status": "error", "message": f"Journey {journey_id} not found"}
                tid = UUID(tenant_id) if tenant_id else uuid4()
                state = await svc.submit(
                    journey,
                    tenant_id=tid,
                    submitted_by="mcp",
                    trace_id=f"mcp:{journey_id}",
                )
                return {
                    "status": "accepted",
                    "execution_id": str(state.execution_id),
                    "journey_id": journey_id,
                    "execution_status": state.status.value,
                }

            if action == "get":
                if not execution_id:
                    return {"status": "error", "message": "execution_id required"}
                state = await svc.get(tenant_id or "", UUID(execution_id))
                if state is None:
                    return {"status": "error", "message": "Execution not found"}
                return {"status": "ok", "execution": state.model_dump(mode="json")}

            if action == "list":
                items = await svc.list_executions(tenant_id or "", journey_id=journey_id)
                return {
                    "status": "ok",
                    "executions": [
                        {
                            "execution_id": str(s.execution_id),
                            "journey_id": s.journey_id,
                            "status": s.status.value,
                        }
                        for s in items
                    ],
                }

            if action == "cancel":
                if not execution_id:
                    return {"status": "error", "message": "execution_id required"}
                state = await svc.cancel(UUID(execution_id))
                return {"status": "ok", "execution_status": state.status.value}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except AdmissionRejectedError as exc:
            return {"status": "rejected", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
