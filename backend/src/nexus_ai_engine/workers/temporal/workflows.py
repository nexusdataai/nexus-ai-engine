"""Temporal workflow + activities for distributed execution (spec 030)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

_runtime: Any = None


def bind_execution_runtime(runtime: Any) -> None:
    global _runtime
    _runtime = runtime


class TickOutcome(str, Enum):
    CONTINUE = "continue"
    DONE = "done"
    WAIT_APPROVAL = "wait_approval"


@dataclass
class ExecutionOutcome:
    execution_id: str
    status: str


try:
    from temporalio import activity, workflow

    @activity.defn(name="executor_tick")
    async def executor_tick(execution_id: str) -> str:
        if _runtime is None:
            raise RuntimeError("execution runtime not bound")
        outcome = await _runtime.run_to_completion(UUID(execution_id), max_ticks=1)
        return outcome.status.value if outcome else "unknown"

    @workflow.defn(name="RunExecutionWorkflow")
    class RunExecutionWorkflow:
        @workflow.run
        async def run(self, execution_id: str) -> ExecutionOutcome:
            while True:
                status = await workflow.execute_activity(
                    executor_tick,
                    execution_id,
                    start_to_close_timeout=workflow.timedelta(minutes=10),
                )
                if status in {"succeeded", "failed", "cancelled", "timed_out"}:
                    return ExecutionOutcome(execution_id=execution_id, status=status)
                await workflow.sleep(1)

    TEMPORAL_AVAILABLE = True
except ImportError:
    RunExecutionWorkflow = None  # type: ignore[misc, assignment]
    executor_tick = None  # type: ignore[assignment]
    TEMPORAL_AVAILABLE = False
