"""Tool package publish API tests (rc2 publish-api)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_ai_engine.testing import make_test_app

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "examples/tool-packages/test-mock/manifest.json"


@pytest.fixture
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


@pytest.mark.asyncio
async def test_publish_tool_package_registers_tools(manifest: dict):
    app = make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/tool-packages", json=manifest)
        assert resp.status_code == 201
        body = resp.json()
        assert body["package_id"] == "test-mock-tools"
        assert body["tools_registered"] == 1

        listed = await client.get("/api/v1/tools")
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1

        detail = await client.get("/api/v1/tools/mock")
        assert detail.status_code == 200
        assert detail.json()["tool_id"] == "mock"


@pytest.mark.asyncio
async def test_publish_rejects_invalid_manifest():
    app = make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/tool-packages", json={"kind": "NotAPackage"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_publish_conflict_on_duplicate(manifest: dict):
    app = make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/tool-packages", json=manifest)
        assert first.status_code == 201
        second = await client.post("/api/v1/tool-packages", json=manifest)
        assert second.status_code == 409
