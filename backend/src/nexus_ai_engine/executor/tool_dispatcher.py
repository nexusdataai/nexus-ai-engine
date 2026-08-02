"""ToolDispatcher — registry tools via ToolRuntime; embedded fallback (docs/spec/040)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from nexus_tool_sdk import ExecutionContext, ToolRuntime

from nexus_ai_engine.contracts.tool_request import (
    ToolError,
    ToolRequest,
    ToolRequestMode,
    ToolResponse,
    ToolResponseStatus,
)
from nexus_ai_engine.executor.embedded_registry import EmbeddedToolRegistry
from nexus_ai_engine.registry.registry import ToolRegistry


@dataclass
class ToolDispatcher:
    registry: ToolRegistry | EmbeddedToolRegistry | None = None
    embedded: EmbeddedToolRegistry = field(default_factory=EmbeddedToolRegistry)
    default_vdl_base_url: str = "http://127.0.0.1:8080/api/v1/vdl"
    default_connector_base_url: str = "http://127.0.0.1:8080/api/v1/connectors"
    _http: httpx.AsyncClient | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.registry, EmbeddedToolRegistry):
            self.embedded = self.registry
            self.registry = None

    async def dispatch(self, request: ToolRequest) -> ToolResponse:
        if self.registry is not None:
            try:
                version = None if request.tool_version in ("", "1.0.0") else request.tool_version
                tool = self.registry.get(request.tool_id, version)
                ontology = self.registry.ontology_api_for(request.tool_id, tool.version)
                vdl_url = ontology.vdl_base_url if ontology else self.default_vdl_base_url
                connector_url = ontology.connector_base_url if ontology else self.default_connector_base_url
                context = ExecutionContext(
                    tenant_id=request.tenant_id,
                    trace_id=request.trace_id,
                    execution_id=request.caller_execution_id,
                    tool_id=request.tool_id,
                    step_id=str(request.caller_node_id),
                    idempotency_key=request.idempotency_key,
                )
                runtime = ToolRuntime.create(
                    context=context,
                    vdl_base_url=vdl_url,
                    connector_base_url=connector_url,
                    http=self._http,
                )
                return await tool.execute(request, runtime)
            except KeyError:
                pass

        now = datetime.now(timezone.utc)
        try:
            payload = await self.embedded.invoke(request.tool_id, dict(request.arguments))
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=now,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=request.tool_id,
                tool_version=request.tool_version,
                capability=request.capability or "nexus-ai",
                status=ToolResponseStatus.OK,
                started_at=now,
                ended_at=now,
                duration_ms=1,
                result=payload,
            )
        except KeyError as exc:
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=now,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=request.tool_id,
                tool_version=request.tool_version,
                capability=request.capability or "nexus-ai",
                status=ToolResponseStatus.ERROR,
                error=ToolError(code="TOOL_NOT_FOUND", message=str(exc), retryable=False),
                started_at=now,
                ended_at=now,
                duration_ms=1,
            )
        except Exception as exc:
            code = "TIMEOUT" if "timeout" in str(exc).lower() else "TOOL_ERROR"
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=now,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=request.tool_id,
                tool_version=request.tool_version,
                capability=request.capability or "nexus-ai",
                status=ToolResponseStatus.ERROR,
                error=ToolError(code=code, message=str(exc), retryable=True),
                started_at=now,
                ended_at=now,
                duration_ms=1,
            )

    def build_request(
        self,
        *,
        tool_id: str,
        arguments: dict,
        tenant_id: UUID,
        trace_id: str,
        execution_id: UUID,
        node_id: UUID,
        attempt: int,
        mode: ToolRequestMode = ToolRequestMode.READ,
        tool_version: str = "1.0.0",
        capability: str = "nexus-ai",
    ) -> ToolRequest:
        return ToolRequest(
            id=uuid4(),
            version=1,
            created_at=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            trace_id=trace_id,
            tool_id=tool_id,
            tool_version=tool_version,
            capability=capability,
            mode=mode,
            idempotency_key=f"{execution_id}:{node_id}:{attempt}",
            caller_execution_id=execution_id,
            caller_node_id=node_id,
            caller_planner_result_id=uuid4(),
            arguments=arguments,
        )

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
