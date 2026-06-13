"""E2E tests for the embedded UI asset serving."""

from __future__ import annotations

import pytest


@pytest.mark.e2e
async def test_root_redirects_to_ui(http_client) -> None:
    resp = await http_client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 308)
    assert resp.headers["location"].endswith("/ui")


@pytest.mark.e2e
async def test_ui_root_returns_html(http_client) -> None:
    resp = await http_client.get("/ui")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "<div id=\"root\">" in body
    assert "/ui/assets/app.js" in body


@pytest.mark.e2e
async def test_ui_assets_served(http_client) -> None:
    for asset, mime_start in (
        ("app.js", ""),
        ("app.css", "text/css"),
        ("favicon.svg", "image/svg"),
    ):
        resp = await http_client.get(f"/ui/assets/{asset}")
        assert resp.status_code == 200, asset
        if mime_start:
            assert resp.headers["content-type"].startswith(mime_start), asset
        assert len(resp.content) > 0, asset


@pytest.mark.e2e
async def test_slim_router_mounted_in_memory_mode(http_client) -> None:
    """Regression guard for the InMemoryEngine branch in `create_app`.

    The harness `app` fixture builds an in-memory engine, so this run
    proves the slim router suite is wired (and, by absence, that the
    legacy router was not). Pairs with
    ``tests/integration/test_production_router_mount.py`` which covers
    the production-Engine branch under moto.
    """
    resp = await http_client.get("/openapi.json")
    assert resp.status_code == 200
    paths = set(resp.json()["paths"].keys())
    # Slim-only path that the embedded UI's v2 page calls.
    assert "/api/v1/schedules/{schedule_id}/run" in paths
    # Legacy-only path must be absent in in-memory mode — otherwise we'd
    # be mounting both router suites and clients would see two different
    # response shapes for the same operation.
    assert "/api/v1/journeys/admin/task-tracker" not in paths
