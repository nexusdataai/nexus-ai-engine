"""Executions API integration tests (rc1 UAT)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from nexus_ai_engine.contracts.execution_state import ExecutionStatus
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.testing import make_test_app

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"


@pytest.fixture
def app():
    application = make_test_app()
    engine: InMemoryEngine = application.state.engine
    raw = yaml.safe_load((EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8"))
    engine.dsl_store.create(JourneyDefinition.model_validate(raw))
    return application


@pytest.mark.asyncio
async def test_submit_execution_returns_202(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/executions/",
            json={"journey_id": "order-to-cash-monitor", "mode": "full"},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["journey_id"] == "order-to-cash-monitor"
    assert "execution_id" in body


@pytest.mark.asyncio
async def test_o2c_execution_completes_via_api(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        submit = await client.post(
            "/api/v1/executions/",
            json={"journey_id": "order-to-cash-monitor", "mode": "full"},
        )
        eid = submit.json()["execution_id"]
        for _ in range(50):
            await asyncio.sleep(0.05)
            detail = await client.get(f"/api/v1/executions/{eid}")
            if detail.json()["status"] == ExecutionStatus.SUCCEEDED.value:
                break
        assert detail.json()["status"] == ExecutionStatus.SUCCEEDED.value
        nodes = await client.get(f"/api/v1/executions/{eid}/nodes")
        assert len(nodes.json()) > 0


@pytest.mark.asyncio
async def test_cancel_execution(app, monkeypatch):
    async def noop(_self, _eid):
        return None

    monkeypatch.setattr(InMemoryEngine, "run_execution_to_completion", noop)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        submit = await client.post(
            "/api/v1/executions/",
            json={"journey_id": "order-to-cash-monitor", "mode": "full"},
        )
        eid = submit.json()["execution_id"]
        cancel = await client.post(f"/api/v1/executions/{eid}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == ExecutionStatus.CANCELLED.value
