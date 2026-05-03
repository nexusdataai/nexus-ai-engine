"""Error-path coverage for the journey/job/schedule HTTP surface."""

from __future__ import annotations


async def test_get_unknown_journey_returns_404(http_client) -> None:
    resp = await http_client.get("/api/v1/journeys/JRN-DOES-NOT-EXIST")
    assert resp.status_code == 404


async def test_run_job_unknown_journey_returns_404(http_client) -> None:
    resp = await http_client.post(
        "/api/v1/journeys/JRN-NOPE/jobs", json={"stage_id": "stg"}
    )
    assert resp.status_code == 404


async def test_run_job_unknown_stage_returns_404(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json={
            "name": "errorpath",
            "stages": [{"id": "real", "name": "real", "order": 1, "status": "pending", "steps": []}],
        },
    )
    jid = created.json()["id"]
    resp = await http_client.post(
        f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "not-a-stage"}
    )
    assert resp.status_code == 404


async def test_invalid_journey_body_is_rejected(http_client) -> None:
    resp = await http_client.post("/api/v1/journeys/", json={"no_name_field": 1})
    assert resp.status_code in (400, 422)


async def test_cancel_unknown_job_returns_404(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json={"name": "x", "stages": [{"id": "stg", "name": "s", "order": 1, "status": "pending", "steps": []}]},
    )
    jid = created.json()["id"]
    resp = await http_client.post(
        f"/api/v1/journeys/{jid}/jobs/JOB-NOPE/cancel"
    )
    assert resp.status_code == 404


async def test_delete_unknown_journey_returns_404(http_client) -> None:
    resp = await http_client.delete("/api/v1/journeys/JRN-NOPE")
    assert resp.status_code == 404
