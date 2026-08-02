"""ExecutionManager — submit + tick loop (docs/spec/020)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from nexus_ai_engine.contracts.execution_graph import ExecutionGraph, NodeKind
from nexus_ai_engine.contracts.execution_state import ExecutionState, ExecutionStatus, NodeState, NodeStatus
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.contracts.tool_request import ToolRequestMode, ToolResponseStatus
from nexus_ai_engine.executor.approval import ApprovalEngine
from nexus_ai_engine.executor.fsm import (
    is_terminal_execution,
    transition_execution,
    transition_node,
)
from nexus_ai_engine.executor.graph import all_nodes_succeeded_or_skipped, all_nodes_terminal, ready_nodes
from nexus_ai_engine.executor.retry import should_retry
from nexus_ai_engine.executor.tool_dispatcher import ToolDispatcher
from nexus_ai_engine.executor.verification import VerificationEngine
from nexus_ai_engine.journeys.compiler import JourneyCompiler


class TickOutcome(str, Enum):
    CONTINUE = "continue"
    DONE = "done"
    WAIT_APPROVAL = "wait_approval"


@dataclass
class SubmitExecutionRequest:
    journey: JourneyDefinition
    tenant_id: UUID
    submitted_by: str = "api"
    trace_id: str = "submit"


@dataclass
class ExecutionManager:
    dispatcher: ToolDispatcher = field(default_factory=ToolDispatcher)
    approvals: ApprovalEngine = field(default_factory=ApprovalEngine)
    verification: VerificationEngine = field(default_factory=VerificationEngine)
    _executions: dict[UUID, ExecutionState] = field(default_factory=dict)
    _graphs: dict[UUID, ExecutionGraph] = field(default_factory=dict)
    _node_results: dict[UUID, dict] = field(default_factory=dict)

    def submit(self, request: SubmitExecutionRequest) -> ExecutionState:
        graph = JourneyCompiler().compile(
            request.journey,
            tenant_id=request.tenant_id,
            trace_id=request.trace_id,
        )
        execution_id = uuid4()
        nodes: dict[str, NodeState] = {}
        for node in graph.nodes:
            nodes[str(node.node_id)] = NodeState(
                node_id=node.node_id,
                step_id=node.display_name or str(node.node_id),
                stage_id="",
                status=NodeStatus.PENDING,
            )
        state = ExecutionState(
            execution_id=execution_id,
            journey_id=request.journey.metadata.id,
            journey_version=request.journey.metadata.version,
            tenant_id=str(request.tenant_id),
            status=ExecutionStatus.PENDING,
            graph_snapshot_id=graph.id,
            nodes=nodes,
            submitted_by=request.submitted_by,
            trace_id=request.trace_id,
        )
        self._executions[execution_id] = state
        self._graphs[execution_id] = graph
        return state

    def get(self, execution_id: UUID) -> ExecutionState | None:
        return self._executions.get(execution_id)

    def get_graph(self, execution_id: UUID) -> ExecutionGraph | None:
        return self._graphs.get(execution_id)

    def list_executions(self) -> list[ExecutionState]:
        return list(self._executions.values())

    async def tick(self, execution_id: UUID) -> TickOutcome:
        state = self._executions.get(execution_id)
        graph = self._graphs.get(execution_id)
        if state is None or graph is None:
            raise KeyError(execution_id)

        if is_terminal_execution(state.status):
            return TickOutcome.DONE

        if state.status is ExecutionStatus.PENDING:
            state.status = transition_execution(state.status, "workflow_started")
            state.started_at = datetime.now(timezone.utc)

        if state.status is ExecutionStatus.AWAITING_APPROVAL:
            if state.approval_ids and all(self.approvals.is_resolved(a) for a in state.approval_ids):
                if all(self.approvals.outcome(a) == "approved" for a in state.approval_ids):
                    state.status = transition_execution(state.status, "approved")
                    state.approval_ids.clear()
                    now = datetime.now(timezone.utc)
                    for ns in state.nodes.values():
                        if ns.status is NodeStatus.RUNNING:
                            ns.status = NodeStatus.SUCCEEDED
                            ns.finished_at = now
                else:
                    state.status = transition_execution(state.status, "rejected")
                    state.finished_at = datetime.now(timezone.utc)
                    return TickOutcome.DONE
            else:
                return TickOutcome.WAIT_APPROVAL

        if state.status is ExecutionStatus.PAUSED:
            return TickOutcome.CONTINUE

        if state.status is ExecutionStatus.RUNNING:
            await self._dispatch_ready_nodes(state, graph)
            if all_nodes_terminal(state):
                if all_nodes_succeeded_or_skipped(state):
                    state.status = transition_execution(state.status, "all_stage_nodes_done")
                else:
                    state.status = transition_execution(state.status, "node_failed_abort")
                    state.finished_at = datetime.now(timezone.utc)
                    return TickOutcome.DONE

        if state.status is ExecutionStatus.VERIFYING:
            if self.verification.run([], {}):
                state.status = transition_execution(state.status, "verification_passed")
                state.finished_at = datetime.now(timezone.utc)
                return TickOutcome.DONE
            state.status = transition_execution(state.status, "verification_failed")
            state.finished_at = datetime.now(timezone.utc)
            return TickOutcome.DONE

        if is_terminal_execution(state.status):
            return TickOutcome.DONE
        return TickOutcome.CONTINUE

    async def run_to_completion(self, execution_id: UUID, *, max_ticks: int = 200) -> ExecutionState:
        for _ in range(max_ticks):
            outcome = await self.tick(execution_id)
            if outcome is TickOutcome.DONE:
                break
        return self._executions[execution_id]

    def pause(self, execution_id: UUID) -> ExecutionState:
        state = self._executions[execution_id]
        if state.status is ExecutionStatus.RUNNING:
            state.status = transition_execution(state.status, "pause")
        return state

    def resume(self, execution_id: UUID) -> ExecutionState:
        state = self._executions[execution_id]
        if state.status is ExecutionStatus.PAUSED:
            state.status = transition_execution(state.status, "resume")
        return state

    def cancel(self, execution_id: UUID) -> ExecutionState:
        state = self._executions[execution_id]
        state.status = transition_execution(state.status, "cancel")
        state.finished_at = datetime.now(timezone.utc)
        return state

    async def _dispatch_ready_nodes(self, state: ExecutionState, graph: ExecutionGraph) -> None:
        tenant = UUID(state.tenant_id) if _is_uuid(state.tenant_id) else uuid4()
        for node_id in ready_nodes(state, graph):
            node = next(n for n in graph.nodes if n.node_id == node_id)
            ns = state.node(node_id)

            if node.kind is NodeKind.APPROVAL:
                ns.status = transition_node(transition_node(ns.status, "dispatch"), "complete")
                ns.finished_at = datetime.now(timezone.utc)
                continue

            if node.kind is NodeKind.NOOP:
                ns.status = transition_node(transition_node(ns.status, "dispatch"), "complete")
                ns.finished_at = datetime.now(timezone.utc)
                continue

            ns.status = transition_node(ns.status, "dispatch")
            ns.attempt += 1
            ns.started_at = datetime.now(timezone.utc)

            if node.kind is NodeKind.TOOL_CALL and node.tool_id:
                req = self.dispatcher.build_request(
                    tool_id=node.tool_id,
                    arguments=node.arguments,
                    tenant_id=tenant,
                    trace_id=state.trace_id,
                    execution_id=state.execution_id,
                    node_id=node_id,
                    attempt=ns.attempt,
                    mode=ToolRequestMode.READ,
                )
                resp = await self.dispatcher.dispatch(req)
                if resp.status is ToolResponseStatus.OK:
                    self._node_results[node_id] = resp.result
                    ns.status = transition_node(ns.status, "complete")
                    ns.finished_at = datetime.now(timezone.utc)
                else:
                    code = resp.error.code if resp.error else "ERROR"
                    if should_retry(node.retry_policy, ns.attempt, code):
                        ns.status = transition_node(transition_node(ns.status, "fail"), "retry")
                    else:
                        ns.status = transition_node(ns.status, "fail")
                        ns.last_error = resp.error.message if resp.error else code
                        ns.finished_at = datetime.now(timezone.utc)
            else:
                ns.status = transition_node(ns.status, "complete")
                ns.finished_at = datetime.now(timezone.utc)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False
