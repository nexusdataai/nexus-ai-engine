"""Persisted execution runtime — manager + DynamoDB repo + admission + SSE."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from nexus_ai_engine.contracts.execution_state import ExecutionState, ExecutionStatus
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.events.sse import SSEManager, emit
from nexus_ai_engine.executor.admission import AdmissionController, AdmissionRejectedError
from nexus_ai_engine.executor.manager import ExecutionManager, SubmitExecutionRequest, TickOutcome

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRuntimeService:
    """Production execution surface for /api/v1/executions."""

    manager: ExecutionManager = field(default_factory=ExecutionManager)
    repository: object | None = None
    admission: AdmissionController = field(default_factory=AdmissionController)
    sse: SSEManager = field(default_factory=SSEManager)
    _background: set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.admission.repository = self.repository

    async def submit(
        self,
        journey: JourneyDefinition,
        *,
        tenant_id: UUID | None = None,
        submitted_by: str = "api",
        trace_id: str = "submit",
        max_parallel_runs: int | None = None,
    ) -> ExecutionState:
        tid = tenant_id or uuid4()
        await self.admission.admit(journey_id=journey.metadata.id, journey_max_parallel=max_parallel_runs)

        state = self.manager.submit(
            SubmitExecutionRequest(
                journey=journey,
                tenant_id=tid,
                submitted_by=submitted_by,
                trace_id=trace_id,
            )
        )
        graph = self.manager.get_graph(state.execution_id)
        if self.repository is not None:
            await self._persist(state)
            if graph is not None:
                await self.repository.put_graph(state.tenant_id, state.execution_id, graph)
        await self.admission.on_started(state.execution_id)
        await self._broadcast(state, "execution.submitted")
        self._spawn_run(state.execution_id)
        return state

    def _spawn_run(self, execution_id: UUID) -> None:
        task = asyncio.create_task(self.run_to_completion(execution_id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _hydrate(self, execution_id: UUID) -> ExecutionState | None:
        state = self.manager.get(execution_id)
        if state is not None:
            return state
        if self.repository is None:
            return None
        state = await self.repository.find_by_execution_id(execution_id)
        if state is None:
            return None
        graph = await self.repository.get_graph(state.tenant_id, execution_id)
        self.manager._executions[execution_id] = state
        if graph is not None:
            self.manager._graphs[execution_id] = graph
        return state

    async def run_to_completion(self, execution_id: UUID, *, max_ticks: int = 500) -> ExecutionState:
        await self._hydrate(execution_id)
        worker_id = f"worker-{uuid4().hex[:8]}"
        acquired = True
        if self.repository is not None:
            acquired = await self.repository.acquire_lock(execution_id, worker_id)
        if not acquired:
            logger.warning("Could not acquire lock for %s", execution_id)
            return self.manager.get(execution_id)  # type: ignore[return-value]

        try:
            terminal_before = None
            for _ in range(max_ticks):
                state = self.manager.get(execution_id)
                if state is None:
                    break
                terminal_before = state.status
                outcome = await self.manager.tick(execution_id)
                state = self.manager.get(execution_id)
                if state and self.repository is not None:
                    await self._persist(state)
                if state:
                    await self._broadcast(state, "execution.tick")
                if outcome is TickOutcome.DONE:
                    break
            state = self.manager.get(execution_id)
            if state and state.status is not terminal_before and state.status in {
                ExecutionStatus.SUCCEEDED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.TIMED_OUT,
            }:
                await self.admission.on_terminal(execution_id)
            return state  # type: ignore[return-value]
        finally:
            if self.repository is not None:
                await self.repository.release_lock(execution_id, worker_id)

    async def get(self, tenant_id: str, execution_id: UUID) -> ExecutionState | None:
        state = await self._hydrate(execution_id)
        if state is not None:
            return state
        if self.repository is not None and tenant_id:
            return await self.repository.get_state(tenant_id, execution_id)
        return None

    async def list_executions(
        self,
        tenant_id: str,
        *,
        journey_id: str | None = None,
        status_filter: str | None = None,
        limit: int = 50,
    ) -> list[ExecutionState]:
        if self.repository is not None:
            return await self.repository.list_executions(
                tenant_id, journey_id=journey_id, status=status_filter, limit=limit
            )
        items = self.manager.list_executions()
        if journey_id:
            items = [s for s in items if s.journey_id == journey_id]
        if status_filter:
            items = [s for s in items if s.status.value == status_filter.lower()]
        return items

    async def cancel(self, execution_id: UUID) -> ExecutionState:
        state = self.manager.cancel(execution_id)
        if self.repository is not None:
            await self._persist(state)
        await self._broadcast(state, "execution.cancelled")
        await self.admission.on_terminal(execution_id)
        return state

    async def pause(self, execution_id: UUID) -> ExecutionState:
        state = self.manager.pause(execution_id)
        if self.repository is not None:
            await self._persist(state)
        await self._broadcast(state, "execution.paused")
        return state

    async def resume(self, execution_id: UUID) -> ExecutionState:
        state = self.manager.resume(execution_id)
        if self.repository is not None:
            await self._persist(state)
        await self._broadcast(state, "execution.resumed")
        self._spawn_run(execution_id)
        return state

    def get_graph(self, execution_id: UUID):
        return self.manager.get_graph(execution_id)

    async def _persist(self, state: ExecutionState) -> None:
        if self.repository is None:
            return
        expected = state.revision
        state.revision += 1
        await self.repository.put_state(state, expected_revision=expected if expected > 1 else None)

    async def _broadcast(self, state: ExecutionState, event_type: str) -> None:
        await self.sse.broadcast(
            emit(
                event_type,
                str(state.execution_id),
                data={
                    "execution_id": str(state.execution_id),
                    "status": state.status.value,
                    "journey_id": state.journey_id,
                    "revision": state.revision,
                },
            )
        )
