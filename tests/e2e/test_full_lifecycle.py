"""End-to-end lifecycle through the HTTP API.

POST journey → POST job → poll /status → GET /logs → GET /reports. These
tests use the deterministic step tools so assertions are stable.
"""

from __future__ import annotations

import asyncio


def _journey_payload(name: str, steps: list[dict]) -> dict:
    return {
        "name": name,
        "description": "e2e lifecycle test",
        "capability": "tests",
        "stages": [
            {
                "id": "stg",
                "name": "Stage",
                "order": 1,
                "status": "pending",
                "steps": steps,
            }
        ],
    }


async def _wait_for_terminal(http_client, jid: str, job_id: str, *, timeout: float = 8.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        resp = await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] != "running":
            return body
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} never terminated within {timeout}s")


async def test_lifecycle_noop(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json=_journey_payload(
            "lifecycle-noop",
            [
                {"id": "s1", "name": "S1", "order": 1, "type": "tool", "tool": "noop"},
                {"id": "s2", "name": "S2", "order": 2, "type": "tool", "tool": "noop"},
            ],
        ),
    )
    assert created.status_code < 400
    jid = created.json()["id"]

    run = await http_client.post(
        f"/api/v1/journeys/{jid}/jobs",
        json={"stage_id": "stg", "triggered_by": "test"},
    )
    assert run.status_code < 400
    job_id = run.json()["id"]

    final = await _wait_for_terminal(http_client, jid, job_id)
    assert final["status"] == "completed"
    assert final["progress"] == 100

    logs = (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/logs")).json()
    # Every deterministic run emits "Starting step X" + "Completed step X" per step.
    step_starts = [e for e in logs if e["message"].startswith("Starting step")]
    assert {e["step_id"] for e in step_starts} == {"s1", "s2"}


async def test_lifecycle_with_reports(http_client) -> None:
    created = await http_client.post(
        "/api/v1/journeys/",
        json=_journey_payload(
            "lifecycle-reports",
            [
                {
                    "id": "rpt1", "name": "Report 1", "order": 1, "type": "tool",
                    "tool": "emit_report",
                    "input": {"title": "First", "summary": "ok"},
                },
                {
                    "id": "rpt2", "name": "Report 2", "order": 2, "type": "tool",
                    "tool": "emit_report",
                    "input": {"title": "Second", "data": {"k": 42}},
                },
            ],
        ),
    )
    jid = created.json()["id"]
    run = await http_client.post(
        f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "stg"}
    )
    job_id = run.json()["id"]
    await _wait_for_terminal(http_client, jid, job_id)

    reports = (await http_client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/reports")).json()
    titles = {r["title"] for r in reports}
    assert titles == {"First", "Second"}
    by_step = {r["step_id"]: r for r in reports}
    assert by_step["rpt1"]["summary"] == "ok"
    assert by_step["rpt2"]["data"] == {"k": 42}
