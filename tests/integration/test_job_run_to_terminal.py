"""Verify the full job lifecycle reaches a stable terminal state.

These tests exercise the deterministic step tools introduced by P1 so
we can assert on exact log contents and step outcomes, not just
"something ran".
"""

from __future__ import annotations

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JobStatus, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


async def _make_journey(engine: InMemoryEngine, steps: list[Step]) -> str:
    j = await engine.create_journey(
        JourneyCreate(
            name="lifecycle",
            stages=[Stage(id="stg", name="Stage", order=1, steps=steps)],
        )
    )
    return j.id


async def test_noop_pipeline_completes_cleanly(engine: InMemoryEngine) -> None:
    jid = await _make_journey(
        engine,
        [
            Step(id=f"s{i}", name=f"S{i}", order=i, type="tool", tool="noop")
            for i in range(1, 4)
        ],
    )
    job = await engine.run_job(jid, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, jid, job.id)

    final = await engine.get_job(jid, job.id)
    assert final is not None
    assert final.status == JobStatus.completed
    assert final.progress == 100
    assert final.error_message in (None, "")
    assert all(s.status == JobStatus.completed and s.progress == 100 for s in final.step_results)


async def test_data_pipeline_flows_through_ctx(engine: InMemoryEngine) -> None:
    jid = await _make_journey(
        engine,
        [
            Step(
                id="extract", name="Extract", order=1, type="tool", tool="transform",
                input={"source": "hello", "fn": "identity", "to_key": "raw"},
            ),
            Step(
                id="upper", name="Upper", order=2, type="tool", tool="transform",
                input={"from_key": "raw", "fn": "upper", "to_key": "shouted"},
            ),
            Step(
                id="count", name="Count", order=3, type="tool", tool="transform",
                input={"from_key": "shouted", "fn": "count", "to_key": "n"},
            ),
        ],
    )
    job = await engine.run_job(jid, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, jid, job.id)

    final = await engine.get_job(jid, job.id)
    assert final is not None and final.status == JobStatus.completed


async def test_fail_after_stops_later_steps(engine: InMemoryEngine) -> None:
    jid = await _make_journey(
        engine,
        [
            Step(id="ok1", name="ok1", order=1, type="tool", tool="noop"),
            Step(
                id="boom", name="boom", order=2, type="tool", tool="fail_after",
                input={"n_ticks": 2, "message": "kaboom"},
            ),
            Step(id="never1", name="never1", order=3, type="tool", tool="noop"),
            Step(id="never2", name="never2", order=4, type="tool", tool="noop"),
        ],
    )
    job = await engine.run_job(jid, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, jid, job.id)

    final = await engine.get_job(jid, job.id)
    assert final is not None
    assert final.status == JobStatus.failed
    assert "kaboom" in (final.error_message or "")
    # Steps 3 and 4 were never started.
    by_id = {s.step_id: s for s in final.step_results}
    assert by_id["ok1"].status == JobStatus.completed
    assert by_id["boom"].status == JobStatus.failed
    assert by_id["never1"].status == JobStatus.queued
    assert by_id["never2"].status == JobStatus.queued


async def test_logs_are_retrievable_and_searchable(engine: InMemoryEngine) -> None:
    jid = await _make_journey(
        engine,
        [
            Step(
                id="logger", name="logger", order=1, type="tool", tool="count_to",
                input={"n": 10, "delay_seconds": 0},
            )
        ],
    )
    job = await engine.run_job(jid, JobRunRequest(stage_id="stg"))
    assert job is not None
    await wait_for_terminal(engine, jid, job.id)

    all_logs = await engine.get_job_logs(jid, job.id)
    # Step start + 10 count lines + step complete >= 12
    assert len(all_logs) >= 12
    # Log ordering: timestamps strictly non-decreasing within a single job.
    ts = [e.timestamp for e in all_logs]
    assert ts == sorted(ts)

    hits = await engine.search_job_logs(jid, job.id, "count 5")
    assert len(hits) == 1 and "count 5/10" in hits[0].message

    errs = await engine.get_job_errors(jid, job.id)
    assert errs == []


async def test_cancel_in_flight(engine: InMemoryEngine) -> None:
    jid = await _make_journey(
        engine,
        [
            Step(
                id="long", name="long", order=1, type="tool", tool="cancel_checkpoint",
                input={"total_seconds": 2.0, "check_every_seconds": 0.05},
            ),
            Step(id="after", name="after", order=2, type="tool", tool="noop"),
        ],
    )
    job = await engine.run_job(jid, JobRunRequest(stage_id="stg"))
    assert job is not None
    # Let the long step start but not finish
    import asyncio

    await asyncio.sleep(0.2)
    await engine.cancel_job(jid, job.id)
    await wait_for_terminal(engine, jid, job.id, timeout=5.0)

    final = await engine.get_job(jid, job.id)
    assert final is not None
    assert final.status == JobStatus.cancelled
    # The noop step after the long one never ran.
    after = next(s for s in final.step_results if s.step_id == "after")
    assert after.status == JobStatus.queued


async def test_retry_succeeds_after_flaky_fail(engine: InMemoryEngine) -> None:
    jid = await _make_journey(
        engine,
        [
            Step(
                id="flaky", name="flaky", order=1, type="tool", tool="flaky",
                input={"seed": 42, "success_rate": 0.0},
            )
        ],
    )
    first = await engine.run_job(jid, JobRunRequest(stage_id="stg"))
    assert first is not None
    await wait_for_terminal(engine, jid, first.id)
    assert (await engine.get_job(jid, first.id)).status == JobStatus.failed

    retried = await engine.retry_job(jid, first.id)
    assert retried is not None and retried.id != first.id
    await wait_for_terminal(engine, jid, retried.id)
    assert (await engine.get_job(jid, retried.id)).status == JobStatus.completed
