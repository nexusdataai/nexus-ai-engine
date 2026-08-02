"""Deterministic MockTool for unit tests."""

from __future__ import annotations

from collections import deque
from typing import Any

from nexus_tool_sdk import ToolRuntime

from nexus_ai_engine.contracts.journey_dsl import RiskClass
from nexus_ai_engine.contracts.tool_descriptor import (
    CapabilityArgumentSpec,
    CapabilityDescriptor,
    PermissionScope,
    ToolAuthor,
    ToolDescriptor,
    ToolSLO,
)
from nexus_ai_engine.contracts.tool_request import ToolRequest
from nexus_ai_engine.tools.base.tool import Tool, ToolExecutionError


class MockTool(Tool):
    tool_id = "mock"
    version = "0.1.0"

    def __init__(self, capabilities: list[str] | None = None) -> None:
        self._queues: dict[str, deque[Any]] = {}
        self._capabilities = capabilities or ["ping"]
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def expect(self, capability: str, response: Any) -> None:
        self._queues.setdefault(capability, deque()).append(response)

    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id=self.tool_id,
            version=self.version,
            display_name="Mock Tool",
            description="Test double",
            category="test",
            author=ToolAuthor(team="platform", contact="team@nexus-ai-engine"),
            provider="mock",
            permission_scope=PermissionScope.TENANT,
            capabilities=[
                CapabilityDescriptor(
                    name=cap,
                    display_name=cap,
                    description=cap,
                    risk_class=RiskClass.READ,
                    reversible=True,
                    idempotent=True,
                    supports_dry_run=True,
                    arguments=[
                        CapabilityArgumentSpec(
                            name="payload",
                            type="object",
                            required=False,
                            description="freeform",
                            json_schema={"type": "object"},
                        )
                    ],
                    output_schema={"type": "object"},
                    required_permissions=[],
                    permission_scope=PermissionScope.TENANT,
                    typical_latency_ms=1,
                    p99_latency_ms=10,
                )
                for cap in self._capabilities
            ],
            slo=ToolSLO(availability_target=0.999, p95_latency_ms=100),
        )

    async def _dispatch(self, request: ToolRequest, runtime: ToolRuntime) -> dict[str, Any]:
        self.calls.append((request.capability, dict(request.arguments)))
        _ = runtime  # available for ontology-aware mock tools
        queue = self._queues.get(request.capability)
        if not queue:
            return {}
        response = queue.popleft()
        if isinstance(response, ToolExecutionError):
            raise response
        return dict(response) if isinstance(response, dict) else {"value": response}
