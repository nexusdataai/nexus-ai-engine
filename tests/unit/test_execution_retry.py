"""Execution retry behavior (rc1-E3)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from nexus_ai_engine.contracts.execution_state import ExecutionStatus, NodeStatus
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.executor.embedded_registry import EmbeddedToolRegistry
from nexus_ai_engine.executor.manager import ExecutionManager, SubmitExecutionRequest
from nexus_ai_engine.executor.tool_dispatcher import ToolDispatcher


_flaky_calls = 0


async def _flaky_tool(_args: dict) -> dict:
    global _flaky_calls
    _flaky_calls += 1
    if _flaky_calls < 2:
        raise TimeoutError("TIMEOUT")
    return {"ok": True}


@pytest.mark.asyncio
async def test_failed_step_retries_per_policy():
    global _flaky_calls
    _flaky_calls = 0

    journey = JourneyDefinition.model_validate(
        {
            "apiVersion": "nexus.ai/v1",
            "kind": "Journey",
            "metadata": {"id": "retry-test", "version": 1},
            "spec": {
                "display_name": "Retry Test",
                "stages": [
                    {
                        "id": "main",
                        "steps": [{"id": "flaky", "tool": "flaky_tool", "params": {}}],
                    }
                ],
            },
        }
    )
    registry = EmbeddedToolRegistry({"flaky_tool": _flaky_tool})
    manager = ExecutionManager(dispatcher=ToolDispatcher(registry))
    state = manager.submit(SubmitExecutionRequest(journey=journey, tenant_id=uuid4()))
    final = await manager.run_to_completion(state.execution_id)
    assert final.status is ExecutionStatus.SUCCEEDED
    node = next(iter(final.nodes.values()))
    assert node.attempt >= 2
    assert node.status is NodeStatus.SUCCEEDED
