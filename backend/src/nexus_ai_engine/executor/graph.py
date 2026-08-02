"""Ready-node scheduler (docs/spec/020)."""

from __future__ import annotations

from uuid import UUID

from nexus_ai_engine.contracts.execution_graph import ExecutionGraph
from nexus_ai_engine.contracts.execution_state import ExecutionState, NodeStatus
from nexus_ai_engine.executor.fsm import transition_node


def _completed_nodes(state: ExecutionState) -> set[UUID]:
    done: set[UUID] = set()
    for ns in state.nodes.values():
        if ns.status in (NodeStatus.SUCCEEDED, NodeStatus.SKIPPED):
            done.add(ns.node_id)
    return done


def promote_ready_nodes(state: ExecutionState, graph: ExecutionGraph) -> None:
    """Transition PENDING nodes whose dependencies are satisfied to READY."""
    done = _completed_nodes(state)
    for node in graph.nodes:
        ns = state.node(node.node_id)
        if ns.status is not NodeStatus.PENDING:
            continue
        if node.depends_on and not all(dep in done for dep in node.depends_on):
            continue
        ns.status = transition_node(ns.status, "deps_satisfied")


def ready_nodes(state: ExecutionState, graph: ExecutionGraph) -> list[UUID]:
    """Return node ids eligible for dispatch this tick."""
    promote_ready_nodes(state, graph)
    running = sum(1 for ns in state.nodes.values() if ns.status is NodeStatus.RUNNING)
    budget = max(0, graph.max_parallelism - running)
    if budget == 0:
        return []

    selected: list[UUID] = []
    for node in graph.nodes:
        ns = state.node(node.node_id)
        if ns.status is not NodeStatus.READY:
            continue
        selected.append(node.node_id)
        if len(selected) >= budget:
            break
    return selected


def all_nodes_terminal(state: ExecutionState) -> bool:
    return all(
        ns.status in (NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.SKIPPED, NodeStatus.ROLLED_BACK)
        for ns in state.nodes.values()
    )


def all_nodes_succeeded_or_skipped(state: ExecutionState) -> bool:
    return all(
        ns.status in (NodeStatus.SUCCEEDED, NodeStatus.SKIPPED) for ns in state.nodes.values()
    )
