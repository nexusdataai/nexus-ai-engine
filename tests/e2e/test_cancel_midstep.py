"""Cancel a job mid-step; verify later steps don't run."""

from __future__ import annotations

import asyncio


async def test_cancel_mid_step_stops_pipeline(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json={
            "name": "cancel-mid",
            "stages": [{
                "id": "stg", "name": "S", "order": 1, "status": "pending",
                "steps": [
                    {
                        "id": "long", "name": "long", "order": 1,
                        "type": "tool", "tool": "cancel_checkpoint",
                        "input": {"total_seconds": 2.0, "check_every_seconds": 0.05},
                    },
                    {"id": "never", "name": "never", "order": 2, "type": "tool", "tool": "noop"},
                ],
            }],
        },
    )
    jid = created.json()["id"]

    run = await http_client.post(f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "stg"})
    job_id = run.json()["id"]

    # Wait for the long step to actually start.
    await asyncio.sleep(0.2)
    cancel = await http_client.post(f"/api/v1/journeys/{jid}/jobs/{job_id}/cancel")
    assert cancel.status_code < 400

    # Wait for terminal.
    for _ in range(200):
        status = (await http_client.get(
            f"/api/v1/journeys/{jid}/jobs/{job_id}/status"
        )).json()["status"]
        if status != "running":
            break
        await asyncio.sleep(0.02)

    final = (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}")).json()
    assert final["status"] == "cancelled"
    step_results = {s["step_id"]: s for s in final["step_results"]}
    assert step_results["never"]["status"] == "queued"
