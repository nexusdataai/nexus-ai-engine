"""Execution context forwarded to ontology APIs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ExecutionContext:
    """Tenant-scoped context for a single tool dispatch."""

    tenant_id: UUID
    trace_id: str
    execution_id: UUID | None = None
    user_id: str | None = None
    tool_id: str | None = None
    step_id: str | None = None
    idempotency_key: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {"tenantId": str(self.tenant_id)}
        if self.execution_id is not None:
            payload["executionId"] = str(self.execution_id)
        if self.step_id is not None:
            payload["stepId"] = self.step_id
        if self.tool_id is not None:
            payload["toolId"] = self.tool_id
        if self.user_id is not None:
            payload["userId"] = self.user_id
        return payload

    def forward_headers(self) -> dict[str, str]:
        headers = {
            "X-Nexus-Tenant-Id": str(self.tenant_id),
            "X-Nexus-Trace-Id": self.trace_id,
        }
        if self.execution_id is not None:
            headers["X-Nexus-Execution-Id"] = str(self.execution_id)
        if self.user_id is not None:
            headers["X-Nexus-User-Id"] = self.user_id
        if self.tool_id is not None:
            headers["X-Nexus-Tool-Id"] = self.tool_id
        if self.step_id is not None:
            headers["X-Nexus-Step-Id"] = self.step_id
        if self.idempotency_key is not None:
            headers["X-Idempotency-Key"] = self.idempotency_key
        return headers
