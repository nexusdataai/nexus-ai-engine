"""E2E tests against the activated journey/job/prompt/schedule API."""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.e2e
async def test_journeys_list_returns_seeded_data(http_client) -> None:
    resp = await http_client.get("/api/v1/journeys/")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 5


@pytest.mark.e2e
async def test_journey_detail_and_stages(http_client) -> None:
    resp = await http_client.get("/api/v1/journeys/")
    journeys = resp.json()
    jid = journeys[0]["id"]

    detail = (await http_client.get(f"/api/v1/journeys/{jid}")).json()
    assert detail["id"] == jid
    assert detail["stages"], "journey must have at least one stage"

    stages = (await http_client.get(f"/api/v1/journeys/{jid}/stages")).json()
    assert stages[0]["id"] == detail["stages"][0]["id"]


@pytest.mark.e2e
async def test_create_and_delete_journey(http_client) -> None:
    create = await http_client.post(
        "/api/v1/journeys/",
        json={"name": "Throwaway", "capability": "demo"},
    )
    assert create.status_code == 201
    new = create.json()

    listed = (await http_client.get("/api/v1/journeys/")).json()
    assert any(j["id"] == new["id"] for j in listed)

    delete = await http_client.delete(f"/api/v1/journeys/{new['id']}")
    assert delete.status_code == 200


@pytest.mark.e2e
async def test_run_and_observe_job(http_client) -> None:
    journeys = (await http_client.get("/api/v1/journeys/")).json()
    j = journeys[0]
    stage_id = j["stages"][0]["id"]

    run = await http_client.post(
        f"/api/v1/journeys/{j['id']}/jobs",
        json={"stage_id": stage_id, "reason": "retry test"},  # retry reason skips random failure
    )
    assert run.status_code == 202
    job = run.json()
    assert job["status"] == "running"

    # Poll status until terminal (bounded)
    for _ in range(400):
        s = (await http_client.get(f"/api/v1/journeys/{j['id']}/jobs/{job['id']}/status")).json()
        if s["status"] != "running":
            assert s["status"] in {"completed", "failed", "cancelled"}
            return
        await asyncio.sleep(0.1)
    raise AssertionError("job did not reach terminal state")


@pytest.mark.e2e
async def test_cancel_job_flow(http_client) -> None:
    journeys = (await http_client.get("/api/v1/journeys/")).json()
    j = journeys[0]
    stage_id = j["stages"][0]["id"]
    job = (await http_client.post(
        f"/api/v1/journeys/{j['id']}/jobs", json={"stage_id": stage_id})
    ).json()

    await asyncio.sleep(0.3)
    cancel = await http_client.post(f"/api/v1/journeys/{j['id']}/jobs/{job['id']}/cancel")
    assert cancel.status_code == 200

    for _ in range(200):
        s = (await http_client.get(f"/api/v1/journeys/{j['id']}/jobs/{job['id']}/status")).json()
        if s["status"] == "cancelled":
            return
        await asyncio.sleep(0.1)
    raise AssertionError("job did not reach cancelled state")


@pytest.mark.e2e
async def test_schedules_crud_and_run_now(http_client) -> None:
    journeys = (await http_client.get("/api/v1/journeys/")).json()
    j = journeys[0]
    stage_id = j["stages"][0]["id"]

    created = await http_client.post(
        "/api/v1/schedules/",
        json={"journey_id": j["id"], "stage_id": stage_id, "interval_minutes": 10},
    )
    assert created.status_code == 201
    sch = created.json()

    patched = await http_client.patch(f"/api/v1/schedules/{sch['id']}", json={"enabled": False})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False

    triggered = await http_client.post(f"/api/v1/schedules/{sch['id']}/run")
    assert triggered.status_code == 202

    deleted = await http_client.delete(f"/api/v1/schedules/{sch['id']}")
    assert deleted.status_code == 200


@pytest.mark.e2e
async def test_prompts_list_update_reset(http_client) -> None:
    prompts = (await http_client.get("/api/v1/prompts")).json()
    assert len(prompts) >= 4

    target = prompts[0]
    updated = await http_client.put(
        f"/api/v1/prompts/{target['id']}", json={"content": "UI-TEST", "note": "unit"}
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["content"] == "UI-TEST"
    assert body["version"] == target["version"] + 1

    audit = (await http_client.get("/api/v1/prompts/audit/log?limit=10")).json()
    assert any(a["prompt_id"] == target["id"] and a["action"] == "updated" for a in audit)

    reset = await http_client.post("/api/v1/prompts/reset")
    assert reset.status_code == 200
    restored = [p for p in reset.json() if p["id"] == target["id"]][0]
    assert restored["content"] == target["content"]


@pytest.mark.e2e
async def test_aggregate_report(http_client) -> None:
    journeys = (await http_client.get("/api/v1/journeys/")).json()
    j = journeys[0]
    resp = await http_client.get(f"/api/v1/journeys/{j['id']}/aggregate-report")
    assert resp.status_code == 200
    body = resp.json()
    assert body["journey_id"] == j["id"]
    assert 0 <= body["success_rate"] <= 100
