"""Journey DSL models (docs/spec/010-journey-dsl.md)."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JourneyTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"


class OnFailure(str, Enum):
    ABORT = "abort"
    CONTINUE = "continue"
    ROLLBACK = "rollback"


class StepKind(str, Enum):
    TOOL_CALL = "tool_call"
    COMPUTE = "compute"
    VERIFY = "verify"
    APPROVAL = "approval"
    NOOP = "noop"


class RiskClass(str, Enum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class VerificationOnFailure(str, Enum):
    ABORT = "abort"
    WARN = "warn"
    IGNORE = "ignore"


class JourneyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9-]+$")
    version: int = Field(ge=1)
    tenant_id: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetrySpec(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_backoff_s: float = Field(default=2.0, ge=0.0)
    max_backoff_s: float = Field(default=60.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    jitter: bool = True
    retryable_errors: list[str] = Field(default_factory=list)


class JourneyDefaults(BaseModel):
    retry: RetrySpec = Field(default_factory=RetrySpec)
    timeout_s: int = Field(default=300, ge=1, le=14400)
    on_failure: OnFailure = OnFailure.ABORT


class JourneyConcurrency(BaseModel):
    max_parallel_runs: int = Field(default=1, ge=1, le=100)
    max_parallel_steps: int = Field(default=4, ge=1, le=64)


class StepVerification(BaseModel):
    check_id: str
    expression: str
    timeout_s: int = Field(default=30, ge=1, le=3600)
    on_failure: VerificationOnFailure = VerificationOnFailure.ABORT


class RollbackStep(BaseModel):
    tool: str | None = None
    type: StepKind | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class RollbackSpec(BaseModel):
    strategy: Literal["none", "explicit", "best_effort"] = "none"
    steps: list[RollbackStep] = Field(default_factory=list)


class JourneyStep(BaseModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    name: str | None = None
    description: str | None = None
    tool: str | None = None
    type: StepKind | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    logic: str | None = None
    output: str | None = None
    foreach: str | None = None
    condition: str | None = None
    parallel: bool = False
    depends_on: list[str] = Field(default_factory=list)
    retry: RetrySpec | None = None
    timeout_s: int | None = Field(default=None, ge=1, le=14400)
    requires_approval: bool = False
    risk_class: RiskClass = RiskClass.READ
    verification: list[StepVerification] = Field(default_factory=list)
    steps: list[JourneyStep] = Field(default_factory=list)

    @field_validator("tool")
    @classmethod
    def _validate_tool_name(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError("tool name must match ^[a-z][a-z0-9_]*$")
        return v


class JourneyStage(BaseModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    name: str | None = None
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    steps: list[JourneyStep] = Field(min_length=1)


class JourneySpec(BaseModel):
    display_name: str = Field(min_length=1, max_length=256)
    description: str = ""
    trigger: JourneyTrigger = JourneyTrigger.MANUAL
    schedule: str | None = None
    defaults: JourneyDefaults = Field(default_factory=JourneyDefaults)
    concurrency: JourneyConcurrency = Field(default_factory=JourneyConcurrency)
    variables: dict[str, Any] = Field(default_factory=dict)
    stages: list[JourneyStage] = Field(min_length=1)
    rollback: RollbackSpec | None = None

    @model_validator(mode="after")
    def _schedule_required_for_trigger(self) -> JourneySpec:
        if self.trigger is JourneyTrigger.SCHEDULE and not self.schedule:
            raise ValueError("schedule is required when trigger is schedule")
        return self


class JourneyDefinition(BaseModel):
    """Root Journey DSL document (YAML/JSON)."""

    model_config = ConfigDict(extra="forbid")

    api_version: Literal["nexus.ai/v1"] = Field(alias="apiVersion")
    kind: Literal["Journey"] = "Journey"
    metadata: JourneyMetadata
    spec: JourneySpec

    @field_validator("spec")
    @classmethod
    def _unique_step_ids(cls, spec: JourneySpec) -> JourneySpec:
        seen: set[str] = set()
        for stage in spec.stages:
            for step in _walk_steps(stage.steps):
                if step.id in seen:
                    raise ValueError(f"duplicate step id: {step.id}")
                seen.add(step.id)
        return spec


JourneyStep.model_rebuild()


def walk_steps(steps: list[JourneyStep]) -> list[JourneyStep]:
    """Return all steps in a stage, including nested parallel groups."""
    out: list[JourneyStep] = []
    for step in steps:
        out.append(step)
        if step.steps:
            out.extend(walk_steps(step.steps))
    return out


# Public aliases (build plan / spec naming)
Journey = JourneyDefinition
Stage = JourneyStage
Step = JourneyStep

_walk_steps = walk_steps  # backward compat for internal callers
