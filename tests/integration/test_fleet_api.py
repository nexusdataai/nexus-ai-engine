"""Fleet API integration tests (v1.0.0)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from nexus_ai_engine.testing import make_test_app


@pytest.fixture
def app():
    return make_test_app()


@pytest.mark.asyncio
async def test_fleet_summary(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/fleet/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "active" in body
    assert "queued" in body
    assert "failed" in body
    assert "workers" in body
    assert "global_limit" in body


@pytest.mark.asyncio
async def test_fleet_metrics(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/fleet/metrics", params={"window": "24h"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_hours"] == 24
    assert "throughput" in body
    assert "tool_dispatch_p95_ms" in body


@pytest.mark.asyncio
async def test_fleet_workers(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/fleet/workers")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["workers"], list)
    assert len(body["workers"]) >= 1
    assert body["workers"][0]["role"] == "api"


@pytest.mark.asyncio
async def test_fleet_summary_updates_prometheus_gauges(app):
    from prometheus_client import generate_latest

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/v1/fleet/summary")
        metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    registry = app.state.metrics_registry
    output = generate_latest(registry).decode()
    assert "nexus_ai_engine_executions_active" in output
