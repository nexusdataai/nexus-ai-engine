"""Executor package — in-process execution engine (docs/spec/020)."""

from .fsm import (
    InvalidTransitionError,
    allowed_execution_events,
    allowed_node_events,
    is_terminal_execution,
    is_terminal_node,
    transition_execution,
    transition_node,
)

__all__ = [
    "InvalidTransitionError",
    "allowed_execution_events",
    "allowed_node_events",
    "is_terminal_execution",
    "is_terminal_node",
    "transition_execution",
    "transition_node",
]
