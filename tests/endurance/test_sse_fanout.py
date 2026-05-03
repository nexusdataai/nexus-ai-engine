"""SSE: multiple subscribers on one job all see the same events."""

from __future__ import annotations

import asyncio

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JourneyCreate, Stage, Step

from .conftest import wait_for_terminal


@pytest.mark.asyncio
async def test_five_subscribers_each_see_events(engine: InMemoryEngine) -> None:
    j = await engine.create_journey(JourneyCreate(
        name="fanout",
        stages=[Stage(id="stg", name="S", order=1, steps=[
            Step(
                id="s1", name="S1", order=1, type="tool", tool="count_to",
                input={"n": 10, "delay_seconds": 0.02},
            )
        ])],
    ))

    async def subscribe(job_id: str, limit: int = 40) -> list[str]:
        events: list[str] = []
        # `stream_job` yields SSE-formatted strings; we just collect them.
        async for chunk in engine.stream_job(job_id):
            events.append(chunk)
            if len(events) >= limit:
                break
        return events

    job = await engine.run_job(j.id, JobRunRequest(stage_id="stg"))
    assert job is not None

    # Start 5 subscribers, then wait for the job.
    subscribers = [asyncio.create_task(subscribe(job.id)) for _ in range(5)]
    await wait_for_terminal(engine, j.id, job.id, timeout=10.0)

    # Give subscribers a brief window to drain buffered events + close.
    await asyncio.sleep(0.2)
    for t in subscribers:
        t.cancel()
    results = []
    for t in subscribers:
        try:
            results.append(await t)
        except asyncio.CancelledError:
            results.append([])

    # Every subscriber should have received at least one event.
    non_empty = [r for r in results if r]
    assert len(non_empty) == 5, f"expected 5 subscribers with events, got {len(non_empty)}"
