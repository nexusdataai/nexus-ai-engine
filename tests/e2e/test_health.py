"""E2E smoke tests that validate the in-process harness works end-to-end."""

from __future__ import annotations

import pytest
from nexus_ai_engine import __version__
from nexus_ai_engine.server.app import create_app


@pytest.mark.e2e
async def test_health_returns_ok(http_client) -> None:
    resp = await http_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


@pytest.mark.e2e
async def test_readiness_reports_engine_state(http_client) -> None:
    resp = await http_client.get("/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["version"] == __version__
    assert body["checks"]["engine"]["status"] == "ok"
    assert body["checks"]["tool_registry"]["status"] == "ok"
    assert body["checks"]["tool_registry"]["mode"] == "plugin_journey"
    assert body["checks"]["dynamodb"]["status"] == "skipped"


@pytest.mark.e2e
async def test_readiness_returns_503_without_engine() -> None:
    from nexus_ai_engine.testing.clients import TestHttpClient

    app = create_app(engine=None)
    async with TestHttpClient(app) as client:
        resp = await client.get("/readiness")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert body["checks"]["engine"]["status"] == "unavailable"


@pytest.mark.e2e
async def test_version_endpoint(http_client) -> None:
    resp = await http_client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "nexus-ai-engine"
    assert body["service"] == "nexus-ai-engine"
    assert body["version"] == __version__
    assert body["env"] == "dev"
    assert isinstance(body["git_sha"], str)


@pytest.mark.e2e
async def test_metrics_endpoint(http_client) -> None:
    resp = await http_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    body = resp.text
    assert "nexus_ai_engine_build_info" in body
    assert __version__ in body


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


@pytest.mark.e2e
async def test_ui_app_js_is_served(http_client) -> None:
    """Alpha smoke: embedded UI bundle is reachable at /ui/assets/app.js."""
    resp = await http_client.get("/ui/assets/app.js")
    assert resp.status_code == 200
    assert len(resp.content) > 1000
    assert "embedded Journey Studio UI" in resp.text
    assert "listJourneys" in resp.text
