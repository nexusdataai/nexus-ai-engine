"""E2E smoke tests that validate the in-process harness works end-to-end."""

from __future__ import annotations

import pytest


@pytest.mark.e2e
async def test_health_returns_ok(http_client) -> None:
    resp = await http_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)


@pytest.mark.e2e
async def test_readiness_reports_engine_state(http_client) -> None:
    resp = await http_client.get("/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert "ready" in body
    assert "version" in body


@pytest.mark.e2e
async def test_version_endpoint(http_client) -> None:
    resp = await http_client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "nexus-ai-engine"


@pytest.mark.e2e
async def test_journeys_list_is_live(http_client) -> None:
    resp = await http_client.get("/api/v1/journeys/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.e2e
async def test_prompts_list_is_live(http_client) -> None:
    resp = await http_client.get("/api/v1/prompts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
