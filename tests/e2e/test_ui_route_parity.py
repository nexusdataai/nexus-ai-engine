"""E2E tests for embedded UI ↔ API route parity (alpha in-memory mode)."""

from __future__ import annotations

import pytest


UI_ROUTES = [
    ("GET", "/health"),
    ("GET", "/version"),
    ("GET", "/readiness"),
    ("GET", "/ui"),
    ("GET", "/ui/assets/app.js"),
    ("GET", "/ui/assets/app.css"),
    ("GET", "/api/v1/journeys/"),
    ("GET", "/api/v1/prompts"),
    ("GET", "/api/v1/prompts/audit/log?limit=5"),
    ("GET", "/api/v1/schedules/"),
    ("GET", "/api/v1/stages/registered"),
]


@pytest.mark.e2e
@pytest.mark.parametrize("method,path", UI_ROUTES)
async def test_ui_static_and_meta_routes(http_client, method: str, path: str) -> None:
    resp = await http_client.request(method, path)
    assert resp.status_code == 200, f"{method} {path} -> {resp.status_code}"


@pytest.mark.e2e
async def test_o2c_and_supply_chain_seeded(http_client) -> None:
    resp = await http_client.get("/api/v1/journeys/")
    journeys = resp.json()
    by_cap = {j["capability"]: j for j in journeys}

    o2c = by_cap["order-to-cash"]
    assert o2c["name"] == "Order-to-Cash Monitor"
    o2c_detail = (await http_client.get(f"/api/v1/journeys/{o2c['id']}")).json()
    assert len(o2c_detail["stages"][0]["steps"]) == 6

    sc = by_cap["supply-chain-risk"]
    assert sc["name"] == "Supply Chain Risk"
    sc_detail = (await http_client.get(f"/api/v1/journeys/{sc['id']}")).json()
    assert sc_detail["status"] == "running"
    assert len(sc_detail["stages"][0]["steps"]) == 4

    jobs = (await http_client.get(f"/api/v1/journeys/{sc['id']}/jobs")).json()
    assert any(j["status"] == "running" for j in jobs)


@pytest.mark.e2e
async def test_ui_journey_routes_for_first_journey(http_client) -> None:
    journeys = (await http_client.get("/api/v1/journeys/")).json()
    j = journeys[0]
    jid = j["id"]
    stage_id = j["stages"][0]["id"]

    assert (await http_client.get(f"/api/v1/journeys/{jid}/status")).status_code == 200
    assert (await http_client.get(f"/api/v1/journeys/{jid}/metrics")).status_code == 200
    assert (await http_client.get(f"/api/v1/journeys/{jid}/stages")).status_code == 200
    assert (await http_client.get(f"/api/v1/journeys/{jid}/aggregate-report")).status_code == 200
    assert (await http_client.get(f"/api/v1/schedules/?journey_id={jid}")).status_code == 200

    run = await http_client.post(
        f"/api/v1/journeys/{jid}/jobs",
        json={"stage_id": stage_id, "reason": "ui parity"},
    )
    assert run.status_code == 202
    job_id = run.json()["id"]

    assert (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/status")).status_code == 200
    assert (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/logs")).status_code == 200
    assert (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/stream/status")).status_code == 200
