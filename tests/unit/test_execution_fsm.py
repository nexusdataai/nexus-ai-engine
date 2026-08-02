"""FSM transition matrix tests (docs/spec/021)."""

from __future__ import annotations

import pytest

from nexus_ai_engine.contracts.execution_state import ExecutionStatus, NodeStatus
from nexus_ai_engine.executor.fsm import (
    EXECUTION_TRANSITIONS,
    NODE_TRANSITIONS,
    InvalidTransitionError,
    is_terminal_execution,
    is_terminal_node,
    transition_execution,
    transition_node,
)


@pytest.mark.parametrize(
    "current,event,expected",
    [(c, e, x) for (c, e), x in EXECUTION_TRANSITIONS.items()],
)
def test_execution_transition_matrix(current, event, expected):
    assert transition_execution(current, event) is expected


@pytest.mark.parametrize(
    "current,event,expected",
    [(c, e, x) for (c, e), x in NODE_TRANSITIONS.items()],
)
def test_node_transition_matrix(current, event, expected):
    assert transition_node(current, event) is expected


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.PENDING,
        ExecutionStatus.RUNNING,
        ExecutionStatus.PAUSED,
        ExecutionStatus.AWAITING_APPROVAL,
        ExecutionStatus.VERIFYING,
        ExecutionStatus.ROLLBACK_PENDING,
        ExecutionStatus.ROLLING_BACK,
    ],
)
def test_cancel_from_non_terminal(status):
    assert transition_execution(status, "cancel") is ExecutionStatus.CANCELLED


@pytest.mark.parametrize(
    "status",
    [ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
)
def test_cancel_rejected_from_terminal(status):
    with pytest.raises(InvalidTransitionError):
        transition_execution(status, "cancel")


def test_invalid_execution_transition():
    with pytest.raises(InvalidTransitionError):
        transition_execution(ExecutionStatus.SUCCEEDED, "workflow_started")


def test_invalid_node_transition():
    with pytest.raises(InvalidTransitionError):
        transition_node(NodeStatus.SUCCEEDED, "dispatch")


def test_terminal_helpers():
    assert is_terminal_execution(ExecutionStatus.SUCCEEDED)
    assert not is_terminal_execution(ExecutionStatus.RUNNING)
    assert is_terminal_node(NodeStatus.SKIPPED)
    assert not is_terminal_node(NodeStatus.READY)
