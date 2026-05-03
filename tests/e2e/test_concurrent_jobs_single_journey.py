"""Launch many jobs against one journey over HTTP, assert isolation."""

from __future__ import annotations

import asyncio


async def _wait(http_client, jid: str, job_id: str, *, timeout: float = 10.0) -> str:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        resp = await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/status")
        s = resp.json()["status"]
        if s != "running":
            return s
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} never terminated")


async def test_ten_jobs_isolated_logs(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json={
            "name": "concurrent-single",
            "stages": [
                {
                    "id": "stg", "name": "S", "order": 1, "status": "pending",
                    "steps": [
                        {"id": "s1", "name": "S1", "order": 1, "type": "tool",
                         "tool": "count_to", "input": {"n": 5, "delay_seconds": 0}}
                    ],
                }
            ],
        },
    )
    jid = created.json()["id"]

    # 10 concurrent runs.
    runs = await asyncio.gather(*[
        http_client.post(f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "stg"})
        for _ in range(10)
    ])
    job_ids = [r.json()["id"] for r in runs]
    assert len(set(job_ids)) == 10

    statuses = await asyncio.gather(*[_wait(http_client, jid, jid_) for jid_ in job_ids])
    assert all(s == "completed" for s in statuses), statuses

    # Each job's logs contain only its own step lines.
    logs_per_job = await asyncio.gather(*[
        http_client.get(f"/api/v1/journeys/{jid}/jobs/{jid_}/logs") for jid_ in job_ids
    ])
    for resp in logs_per_job:
        logs = resp.json()
        step_ids = {e["step_id"] for e in logs}
        assert step_ids == {"s1"}
        # Should contain all 5 count lines
        count_lines = [e for e in logs if "count " in e["message"]]
        assert len(count_lines) == 5
