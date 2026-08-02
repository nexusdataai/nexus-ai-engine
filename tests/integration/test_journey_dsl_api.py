"""Integration tests for Journey DSL HTTP API."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from nexus_ai_engine.testing import make_test_app

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"


@pytest.fixture
def app():
    return make_test_app()


@pytest.mark.asyncio
async def test_post_validate_accepts_o2c_yaml(app):
    yaml_body = (EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/journeys/validate",
            content=yaml_body,
            headers={"Content-Type": "application/yaml"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True


@pytest.mark.asyncio
async def test_create_journey_and_list_versions(app):
    yaml_body = (EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post(
            "/api/v1/journeys/import",
            content=yaml_body,
            headers={"Content-Type": "application/yaml"},
        )
        assert create.status_code == 201
        versions = await client.get("/api/v1/journeys/order-to-cash-monitor/versions")
        assert versions.status_code == 200
        assert versions.json() == [1]
