"""Execution state models (docs/spec/021-execution-state-machine.md)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLING_BACK = "rolling_back"


class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class StageRunStatus(str, Enum):
    """Legacy job status mapping (spec 021)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeState(BaseModel):
    node_id: UUID
    step_id: str = ""
    stage_id: str = ""
    status: NodeStatus = NodeStatus.PENDING
    attempt: int = 0
    last_error: str | None = None
    result_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExecutionState(BaseModel):
    execution_id: UUID
    journey_id: str
    journey_version: int
    tenant_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    revision: int = 1

    current_stage_id: str | None = None
    current_stage_index: int = 0

    graph_snapshot_id: UUID
    nodes: dict[str, NodeState] = Field(default_factory=dict)

    approval_ids: list[UUID] = Field(default_factory=list)
    rollback_in_progress: bool = False

    started_at: datetime | None = None
    finished_at: datetime | None = None
    deadline_at: datetime | None = None

    submitted_by: str = "system"
    trace_id: str = ""
    labels: dict[str, str] = Field(default_factory=dict)

    def node(self, node_id: UUID) -> NodeState:
        return self.nodes[str(node_id)]

    def set_node(self, node_state: NodeState) -> None:
        self.nodes[str(node_state.node_id)] = node_state
