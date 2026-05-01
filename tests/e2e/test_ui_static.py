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
