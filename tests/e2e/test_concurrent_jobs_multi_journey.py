"""Concurrent jobs across multiple journeys; verify per-journey aggregates."""

from __future__ import annotations

import asyncio


async def _wait(http_client, jid: str, job_id: str, *, timeout: float = 10.0) -> str:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        s = (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/status")).json()["status"]
        if s != "running":
            return s
        await asyncio.sleep(0.02)
    raise AssertionError("timeout")


async def test_five_journeys_three_jobs_each(http_client) -> None:
    payload = {
        "stages": [
            {
                "id": "stg", "name": "S", "order": 1, "status": "pending",
                "steps": [{"id": "s1", "name": "S1", "order": 1, "type": "tool", "tool": "noop"}],
            }
        ]
    }
    # Create 5 journeys concurrently.
    creations = await asyncio.gather(*[
        http_client.post("/api/v1/journeys/", json={"name": f"J{i}", **payload})
        for i in range(5)
    ])
    jids = [r.json()["id"] for r in creations]
    assert len(set(jids)) == 5

    # 15 concurrent job runs: 3 per journey.
    runs = await asyncio.gather(*[
        http_client.post(f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "stg"})
        for jid in jids for _ in range(3)
    ])
    job_infos = [(r.json()["journey_id"], r.json()["id"]) for r in runs]

    await asyncio.gather(*[_wait(http_client, jid, job_id) for jid, job_id in job_infos])

    # Per-journey aggregates: 3 total, 3 done, 0 running/failed.
    for jid in jids:
        resp = await http_client.get(f"/api/v1/journeys/{jid}")
        body = resp.json()
        assert body["jobs_total"] == 3
        assert body["jobs_done"] == 3
        assert body["jobs_running"] == 0
        assert body["jobs_failed"] == 0
