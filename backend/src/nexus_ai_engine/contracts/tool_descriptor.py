"""ToolDescriptor (aligned with nexus-sre docs/contracts/031-tool-descriptor.md)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nexus_ai_engine.contracts.journey_dsl import RiskClass


class PermissionScope(str, Enum):
    CLUSTER = "cluster"
    NAMESPACE = "namespace"
    ACCOUNT = "account"
    REGION = "region"
    TENANT = "tenant"
    GLOBAL = "global"


class CapabilityArgumentSpec(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str = Field(max_length=1024)
    json_schema: dict[str, Any]
    example: Any | None = None


class CapabilityDescriptor(BaseModel):
    name: str
    display_name: str
    description: str = Field(max_length=2048)
    risk_class: RiskClass
    reversible: bool
    idempotent: bool
    supports_dry_run: bool
    arguments: list[CapabilityArgumentSpec]
    output_schema: dict[str, Any]
    required_permissions: list[str]
    permission_scope: PermissionScope
    typical_latency_ms: int = Field(ge=0)
    p99_latency_ms: int = Field(ge=0)
    rate_limit_per_minute: int | None = None


class ToolSLO(BaseModel):
    availability_target: float = Field(ge=0.9, le=1.0)
    p95_latency_ms: int = Field(ge=0)
    error_budget_burn_alert_ratio: float = Field(default=2.0, ge=1.0)


class ToolAuthor(BaseModel):
    team: str
    contact: str


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str
    version: str
    schema_url: str = "nexus.sre/contracts/tool-descriptor/v1"

    display_name: str
    description: str = Field(max_length=4096)
    category: str
    author: ToolAuthor

    provider: str
    provider_min_version: str | None = None
    permission_scope: PermissionScope

    capabilities: list[CapabilityDescriptor] = Field(min_length=1)
    slo: ToolSLO
    tags: list[str] = Field(default_factory=list)

    replay_supported: bool = True
