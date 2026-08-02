"""ToolRequest and ToolResponse (aligned with nexus-sre docs/contracts/030-tool-request-response.md)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolRequestMode(str, Enum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ToolCredentialRef(BaseModel):
    kind: str
    scope: str
    secret_ref: str


class ToolRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: int = Field(ge=1)
    schema_url: str = "nexus.sre/contracts/tool-request/v1"
    created_at: datetime
    tenant_id: UUID
    trace_id: str

    tool_id: str
    tool_version: str
    capability: str
    mode: ToolRequestMode

    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_s: int = Field(default=60, ge=1, le=3600)
    idempotency_key: str = Field(min_length=1, max_length=128)

    caller_execution_id: UUID
    caller_node_id: UUID
    caller_planner_result_id: UUID

    credentials: list[ToolCredentialRef] = Field(default_factory=list)
    target_scope: dict[str, str] = Field(default_factory=dict)

    dry_run: bool = False


class ToolResponseStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolError(BaseModel):
    code: str
    message: str = Field(max_length=2048)
    retryable: bool
    upstream_status: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: int = Field(ge=1)
    schema_url: str = "nexus.sre/contracts/tool-response/v1"
    created_at: datetime
    tenant_id: UUID
    trace_id: str

    request_id: UUID
    tool_id: str
    tool_version: str
    capability: str

    status: ToolResponseStatus
    error: ToolError | None = None

    result: dict[str, Any] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)

    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    upstream_latency_ms: int | None = None

    cost_estimate_usd: float | None = None
    idempotency_hit: bool = False
