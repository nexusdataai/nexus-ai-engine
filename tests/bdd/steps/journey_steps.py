"""Shared BDD steps for journey/job lifecycle, concurrency, cancellation."""

from __future__ import annotations

import asyncio
import time

from behave import given, then, when

# ── Helpers ──────────────────────────────────────────────────────────────


def _build_payload(name: str, steps: list[dict]) -> dict:
    return {
        "name": name,
        "description": f"bdd scenario for {name}",
        "capability": "bdd",
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


async def _create_journey(context, name: str, steps: list[dict]) -> str:
    resp = await context.client.post("/api/v1/journeys/", json=_build_payload(name, steps))
    assert resp.status_code < 400, f"{resp.status_code}: {resp.text}"
    return resp.json()["id"]


async def _run_job(context, jid: str) -> str:
    resp = await context.client.post(f"/api/v1/journeys/{jid}/jobs", json={"stage_id": "stg"})
    assert resp.status_code < 400, f"{resp.status_code}: {resp.text}"
    return resp.json()["id"]


async def _wait_terminal(context, jid: str, job_id: str, timeout: float = 8.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = await context.client.get(f"/api/v1/journeys/{jid}/jobs/{job_id}/status")
        body = resp.json()
        if body["status"] != "running":
            return body["status"]
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} never terminated")


# ── Givens: construct journeys ──────────────────────────────────────────


@given('a journey with {n:d} noop steps named "{name}"')
def step_journey_with_n_noops(context, n: int, name: str) -> None:
    steps = [
        {"id": f"s{i}", "name": f"S{i}", "order": i, "type": "tool", "tool": "noop"}
        for i in range(1, n + 1)
    ]
    context.journey_id = context.loop.run_until_complete(_create_journey(context, name, steps))


@given('a journey with a deterministic failing step named "{name}"')
def step_journey_with_fail(context, name: str) -> None:
    steps = [
        {"id": "ok", "name": "ok", "order": 1, "type": "tool", "tool": "noop"},
        {
            "id": "boom", "name": "boom", "order": 2, "type": "tool", "tool": "fail_after",
            "input": {"n_ticks": 2, "message": "boom"},
        },
        {"id": "never", "name": "never", "order": 3, "type": "tool", "tool": "noop"},
    ]
    context.journey_id = context.loop.run_until_complete(_create_journey(context, name, steps))


@given('a journey with a long-running cancelable step named "{name}"')
def step_journey_with_long(context, name: str) -> None:
    steps = [
        {
            "id": "long", "name": "long", "order": 1, "type": "tool",
            "tool": "cancel_checkpoint",
            "input": {"total_seconds": 3.0, "check_every_seconds": 0.05},
        },
        {"id": "never", "name": "never", "order": 2, "type": "tool", "tool": "noop"},
    ]
    context.journey_id = context.loop.run_until_complete(_create_journey(context, name, steps))


@given('a journey with a flaky step named "{name}"')
def step_journey_with_flaky(context, name: str) -> None:
    steps = [{
        "id": "flaky", "name": "flaky", "order": 1, "type": "tool", "tool": "flaky",
        "input": {"seed": 7, "success_rate": 0.0},
    }]
    context.journey_id = context.loop.run_until_complete(_create_journey(context, name, steps))


@given('a journey that emits {n:d} reports named "{name}"')
def step_journey_with_reports(context, n: int, name: str) -> None:
    steps = [
        {
            "id": f"r{i}", "name": f"R{i}", "order": i, "type": "tool", "tool": "emit_report",
            "input": {"title": f"Report {i}", "summary": f"summary {i}"},
        }
        for i in range(1, n + 1)
    ]
    context.journey_id = context.loop.run_until_complete(_create_journey(context, name, steps))


# ── Whens: actions ──────────────────────────────────────────────────────


@when('I start a job on the journey')
def step_start_job(context) -> None:
    assert context.journey_id, "no journey created; did a Given run?"
    context.job_id = context.loop.run_until_complete(_run_job(context, context.journey_id))


@when('I start {n:d} jobs on the journey')
def step_start_n_jobs(context, n: int) -> None:
    async def _burst():
        return await asyncio.gather(*[
            _run_job(context, context.journey_id) for _ in range(n)
        ])

    context.job_ids = context.loop.run_until_complete(_burst())


@when('I wait for the job to reach a terminal state')
def step_wait_terminal(context) -> None:
    context.final_status = context.loop.run_until_complete(
        _wait_terminal(context, context.journey_id, context.job_id)
    )


@when('I wait for all jobs to reach a terminal state')
def step_wait_all_terminal(context) -> None:
    async def _wait_all():
        return await asyncio.gather(*[
            _wait_terminal(context, context.journey_id, jid) for jid in context.job_ids
        ])

    context.final_statuses = context.loop.run_until_complete(_wait_all())


@when('I cancel the job')
def step_cancel_job(context) -> None:
    async def _cancel():
        # Small lead-in so the tool is actually running.
        await asyncio.sleep(0.1)
        return await context.client.post(
            f"/api/v1/journeys/{context.journey_id}/jobs/{context.job_id}/cancel"
        )

    resp = context.loop.run_until_complete(_cancel())
    assert resp.status_code < 400, resp.text


@when('I retry the job')
def step_retry_job(context) -> None:
    resp = context.loop.run_until_complete(
        context.client.post(
            f"/api/v1/journeys/{context.journey_id}/jobs/{context.job_id}/retry"
        )
    )
    assert resp.status_code < 400, resp.text
    context.job_id = resp.json()["id"]


# ── Thens: assertions ──────────────────────────────────────────────────


@then('the job ends with status "{status}"')
def step_job_ends_with(context, status: str) -> None:
    assert context.final_status == status, context.final_status


@then('all jobs end with status "{status}"')
def step_all_jobs_end_with(context, status: str) -> None:
    assert all(s == status for s in context.final_statuses), context.final_statuses


@then('step "{step_id}" has status "{status}"')
def step_step_status(context, step_id: str, status: str) -> None:
    body = context.loop.run_until_complete(
        context.client.get(f"/api/v1/journeys/{context.journey_id}/jobs/{context.job_id}")
    ).json()
    step = next(s for s in body["step_results"] if s["step_id"] == step_id)
    assert step["status"] == status, step


@then('the job has at least {n:d} logs')
def step_job_has_logs(context, n: int) -> None:
    logs = context.loop.run_until_complete(
        context.client.get(f"/api/v1/journeys/{context.journey_id}/jobs/{context.job_id}/logs")
    ).json()
    assert len(logs) >= n, f"expected >= {n} logs, got {len(logs)}"


@then('the journey has {n:d} jobs')
def step_journey_has_n_jobs(context, n: int) -> None:
    body = context.loop.run_until_complete(
        context.client.get(f"/api/v1/journeys/{context.journey_id}")
    ).json()
    assert body["jobs_total"] == n, body


@then('the job has {n:d} reports')
def step_job_has_reports(context, n: int) -> None:
    reports = context.loop.run_until_complete(
        context.client.get(
            f"/api/v1/journeys/{context.journey_id}/jobs/{context.job_id}/reports"
        )
    ).json()
    assert len(reports) == n, reports
