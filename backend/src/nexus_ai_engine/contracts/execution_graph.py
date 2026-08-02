"""ExecutionGraph (aligned with nexus-sre docs/contracts/020-execution-graph.md)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeKind(str, Enum):
    TOOL_CALL = "tool_call"
    VERIFY = "verify"
    APPROVAL = "approval"
    NOOP = "noop"


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_backoff_s: float = Field(default=1.0, ge=0.0, le=60.0)
    max_backoff_s: float = Field(default=60.0, ge=0.0, le=3600.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter: bool = True
    retryable_error_codes: list[str] = Field(default_factory=list)


class NodeVerification(BaseModel):
    check_id: str
    expression: str
    tolerance: float = 0.0
    timeout_s: int = Field(default=60, ge=1, le=3600)


class ExecutionNode(BaseModel):
    node_id: UUID
    kind: NodeKind
    tool_id: str | None = None
    capability: str | None = None
    arguments: dict = Field(default_factory=dict)

    timeout_s: int = Field(default=300, ge=1, le=14400)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    verification: list[NodeVerification] = Field(default_factory=list)

    depends_on: list[UUID] = Field(default_factory=list)
    can_parallel: bool = True

    risk_class: str = "read"
    requires_approval: bool = False
    approval_ref: UUID | None = None

    rollback_node_id: UUID | None = None
    on_failure: str = "abort"

    display_name: str = Field(default="", max_length=128)
    reason: str = Field(default="", max_length=1024)


class ExecutionEdge(BaseModel):
    from_node: UUID
    to_node: UUID
    kind: str = "data"
    condition: str | None = None


class ExecutionGraph(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: int = Field(ge=1)
    schema_url: str = "nexus.sre/contracts/execution-graph/v1"
    created_at: datetime
    tenant_id: UUID
    trace_id: str

    planner_result_id: UUID
    nodes: list[ExecutionNode] = Field(min_length=1, max_length=200)
    edges: list[ExecutionEdge] = Field(default_factory=list)

    max_parallelism: int = Field(default=4, ge=1, le=64)
    max_wall_clock_s: int = Field(default=3600, ge=60, le=86400)

    content_sha256: str

    @model_validator(mode="after")
    def _validate_dag(self) -> ExecutionGraph:
        node_ids = {n.node_id for n in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("node_id values must be unique")
        for node in self.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(f"node {node.node_id} depends on unknown {dep}")
            if node.kind is NodeKind.TOOL_CALL and (not node.tool_id or not node.capability):
                raise ValueError(f"TOOL_CALL node {node.node_id} missing tool_id/capability")
            if node.kind is NodeKind.APPROVAL and (node.tool_id or not node.requires_approval):
                raise ValueError(
                    f"APPROVAL node {node.node_id} must have tool_id=None and requires_approval=True"
                )
        if _has_cycle(self.nodes):
            raise ValueError("graph contains a cycle")
        return self

    @staticmethod
    def compute_content_sha256(
        nodes: list[ExecutionNode],
        edges: list[ExecutionEdge],
        max_parallelism: int,
        max_wall_clock_s: int,
    ) -> str:
        payload = {
            "nodes": [n.model_dump(mode="json", exclude_none=False) for n in nodes],
            "edges": [e.model_dump(mode="json", exclude_none=False) for e in edges],
            "max_parallelism": max_parallelism,
            "max_wall_clock_s": max_wall_clock_s,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _has_cycle(nodes: list[ExecutionNode]) -> bool:
    graph: dict[UUID, list[UUID]] = {n.node_id: list(n.depends_on) for n in nodes}
    white, gray, black = 0, 1, 2
    color: dict[UUID, int] = dict.fromkeys(graph.keys(), white)

    def visit(u: UUID) -> bool:
        color[u] = gray
        for v in graph.get(u, []):
            if color.get(v) == gray:
                return True
            if color.get(v) == white and visit(v):
                return True
        color[u] = black
        return False

    return any(color[u] == white and visit(u) for u in list(graph.keys()))
