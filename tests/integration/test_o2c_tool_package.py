"""Strict tool validation against published catalog."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_ai_engine.testing import make_test_app

O2C_MANIFEST = Path(__file__).resolve().parents[2] / "examples/tool-packages/o2c/manifest.json"


@pytest.mark.asyncio
async def test_strict_validation_rejects_unknown_after_o2c_publish():
    manifest = json.loads(O2C_MANIFEST.read_text())
    app = make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pub = await client.post("/api/v1/tool-packages", json=manifest)
        assert pub.status_code == 201

        bad_journey = {
            "apiVersion": "nexus.ai/v1",
            "kind": "Journey",
            "metadata": {"id": "strict-catalog", "version": 1},
            "spec": {
                "display_name": "Strict",
                "stages": [
                    {
                        "id": "main",
                        "steps": [{"id": "s1", "tool": "not_in_catalog_xyz"}],
                    }
                ],
            },
        }
        resp = await client.post("/api/v1/journeys/validate?strict_tools=true", json=bad_journey)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert any(e["code"] == "unknown_tool" for e in body["errors"])


@pytest.mark.asyncio
async def test_strict_validation_accepts_o2c_tool():
    manifest = json.loads(O2C_MANIFEST.read_text())
    app = make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/tool-packages", json=manifest)
        journey = {
            "apiVersion": "nexus.ai/v1",
            "kind": "Journey",
            "metadata": {"id": "o2c-strict", "version": 1},
            "spec": {
                "display_name": "O2C",
                "stages": [
                    {
                        "id": "match",
                        "steps": [
                            {
                                "id": "m1",
                                "tool": "o2c_match_order_delivery_invoice",
                                "params": {"opportunity_id": "OPP-1"},
                            }
                        ],
                    }
                ],
            },
        }
        resp = await client.post("/api/v1/journeys/validate?strict_tools=true", json=journey)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True
