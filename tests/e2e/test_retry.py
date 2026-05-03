"""Retry a failed job via the HTTP API."""

from __future__ import annotations

import asyncio


async def test_retry_spawns_new_job_that_completes(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json={
            "name": "retry-me",
            "stages": [{
                "id": "stg", "name": "S", "order": 1, "status": "pending",
                "steps": [{
                    "id": "flaky", "name": "flaky", "order": 1,
                    "type": "tool", "tool": "flaky",
                    "input": {"seed": 7, "success_rate": 0.0},
                }],
            }],
        },
    )
    jid = created.json()["id"]

    first = await http_client.post(f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "stg"})
    first_id = first.json()["id"]

    # Wait for first failure.
    for _ in range(400):
        s = (await http_client.get(
            f"/api/v1/journeys/{jid}/jobs/{first_id}/status"
        )).json()["status"]
        if s != "running":
            break
        await asyncio.sleep(0.02)
    assert s == "failed"

    # Retry.
    retry_resp = await http_client.post(f"/api/v1/journeys/{jid}/jobs/{first_id}/retry")
    assert retry_resp.status_code < 400
    retry_id = retry_resp.json()["id"]
    assert retry_id != first_id

    for _ in range(400):
        s = (await http_client.get(
            f"/api/v1/journeys/{jid}/jobs/{retry_id}/status"
        )).json()["status"]
        if s != "running":
            break
        await asyncio.sleep(0.02)

    assert s == "completed"
