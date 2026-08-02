"""Execution FSM — transition validation per docs/spec/021."""

from __future__ import annotations

from nexus_ai_engine.contracts.execution_state import ExecutionStatus, NodeStatus

TERMINAL_EXECUTION: frozenset[ExecutionStatus] = frozenset(
    {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    }
)

TERMINAL_NODE: frozenset[NodeStatus] = frozenset(
    {
        NodeStatus.SUCCEEDED,
        NodeStatus.FAILED,
        NodeStatus.SKIPPED,
        NodeStatus.ROLLED_BACK,
    }
)

EXECUTION_TRANSITIONS: dict[tuple[ExecutionStatus, str], ExecutionStatus] = {
    (ExecutionStatus.PENDING, "workflow_started"): ExecutionStatus.RUNNING,
    (ExecutionStatus.PENDING, "approval_required"): ExecutionStatus.AWAITING_APPROVAL,
    (ExecutionStatus.AWAITING_APPROVAL, "approved"): ExecutionStatus.RUNNING,
    (ExecutionStatus.AWAITING_APPROVAL, "rejected"): ExecutionStatus.FAILED,
    (ExecutionStatus.RUNNING, "all_stage_nodes_done"): ExecutionStatus.VERIFYING,
    (ExecutionStatus.RUNNING, "pause"): ExecutionStatus.PAUSED,
    (ExecutionStatus.RUNNING, "node_failed_abort"): ExecutionStatus.ROLLBACK_PENDING,
    (ExecutionStatus.RUNNING, "timeout"): ExecutionStatus.TIMED_OUT,
    (ExecutionStatus.PAUSED, "resume"): ExecutionStatus.RUNNING,
    (ExecutionStatus.VERIFYING, "verification_passed"): ExecutionStatus.SUCCEEDED,
    (ExecutionStatus.VERIFYING, "verification_failed"): ExecutionStatus.ROLLBACK_PENDING,
    (ExecutionStatus.ROLLBACK_PENDING, "rollback_started"): ExecutionStatus.ROLLING_BACK,
    (ExecutionStatus.ROLLING_BACK, "rollback_done"): ExecutionStatus.FAILED,
}

NODE_TRANSITIONS: dict[tuple[NodeStatus, str], NodeStatus] = {
    (NodeStatus.PENDING, "deps_satisfied"): NodeStatus.READY,
    (NodeStatus.READY, "dispatch"): NodeStatus.RUNNING,
    (NodeStatus.RUNNING, "complete"): NodeStatus.SUCCEEDED,
    (NodeStatus.RUNNING, "fail"): NodeStatus.FAILED,
    (NodeStatus.RUNNING, "skip"): NodeStatus.SKIPPED,
    (NodeStatus.FAILED, "retry"): NodeStatus.READY,
    (NodeStatus.FAILED, "rollback"): NodeStatus.ROLLED_BACK,
}


class InvalidTransitionError(ValueError):
    """Raised when an FSM event is not valid for the current state."""


def is_terminal_execution(status: ExecutionStatus) -> bool:
    return status in TERMINAL_EXECUTION


def is_terminal_node(status: NodeStatus) -> bool:
    return status in TERMINAL_NODE


def transition_execution(current: ExecutionStatus, event: str) -> ExecutionStatus:
    if event == "cancel":
        if is_terminal_execution(current):
            raise InvalidTransitionError(f"cannot cancel terminal execution {current.value}")
        return ExecutionStatus.CANCELLED
    key = (current, event)
    if key not in EXECUTION_TRANSITIONS:
        raise InvalidTransitionError(f"invalid execution transition: {current.value} + {event}")
    return EXECUTION_TRANSITIONS[key]


def transition_node(current: NodeStatus, event: str) -> NodeStatus:
    key = (current, event)
    if key not in NODE_TRANSITIONS:
        raise InvalidTransitionError(f"invalid node transition: {current.value} + {event}")
    return NODE_TRANSITIONS[key]


def allowed_execution_events(status: ExecutionStatus) -> list[str]:
    events = [ev for (st, ev) in EXECUTION_TRANSITIONS if st == status]
    if not is_terminal_execution(status):
        events.append("cancel")
    return sorted(set(events))


def allowed_node_events(status: NodeStatus) -> list[str]:
    return sorted({ev for (st, ev) in NODE_TRANSITIONS if st == status})
