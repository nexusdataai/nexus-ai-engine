"""O2C journey compile + in-process execution E2E (rc1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from nexus_ai_engine.contracts.execution_state import ExecutionStatus, NodeStatus
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.executor.legacy_adapter import LegacyStageAdapter
from nexus_ai_engine.executor.manager import ExecutionManager, SubmitExecutionRequest
from nexus_ai_engine.journeys.validator import JourneyValidator

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"


def _load_o2c() -> JourneyDefinition:
    raw = yaml.safe_load((EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8"))
    assert JourneyValidator().validate(raw).valid
    return JourneyDefinition.model_validate(raw)


@pytest.mark.asyncio
async def test_o2c_journey_executes_to_completion():
    journey = _load_o2c()
    manager = ExecutionManager()
    state = manager.submit(
        SubmitExecutionRequest(journey=journey, tenant_id=uuid4(), trace_id="e2e-o2c")
    )
    final = await manager.run_to_completion(state.execution_id)
    assert final.status is ExecutionStatus.SUCCEEDED
    assert all(
        ns.status in (NodeStatus.SUCCEEDED, NodeStatus.SKIPPED) for ns in final.nodes.values()
    )


def test_legacy_stage_adapter_order_to_cash_registered():
    assert LegacyStageAdapter.is_registered("order_to_cash")
