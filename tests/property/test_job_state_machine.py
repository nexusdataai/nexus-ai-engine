"""Job state-machine invariants.

A Job transitions through statuses: queued -> running -> one of
(completed, failed, cancelled). Hypothesis explores interleavings of
start/cancel/wait and asserts no illegal transitions occur.
"""

from __future__ import annotations

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import JobRunRequest, JobStatus, JourneyCreate, Stage, Step
from tests.fixtures.steps import register_all

TERMINAL = {JobStatus.completed, JobStatus.failed, JobStatus.cancelled}
ALLOWED_NEXT: dict[JobStatus, set[JobStatus]] = {
    JobStatus.queued: {JobStatus.queued, JobStatus.running, JobStatus.cancelled},
    JobStatus.running: {JobStatus.running, JobStatus.completed, JobStatus.failed, JobStatus.cancelled},
    JobStatus.completed: {JobStatus.completed},
    JobStatus.failed: {JobStatus.failed},
    JobStatus.cancelled: {JobStatus.cancelled},
}


@given(
    n_steps=st.integers(min_value=1, max_value=4),
    cancel_after_ms=st.integers(min_value=0, max_value=80),
)
async def test_no_illegal_status_transitions(n_steps: int, cancel_after_ms: int) -> None:
    engine = InMemoryEngine()
    register_all(engine)
    journey = await engine.create_journey(
        JourneyCreate(
            name="sm",
            stages=[
                Stage(
                    id="stg", name="S", order=1,
                    steps=[
                        Step(id=f"s{i}", name=f"S{i}", order=i, type="tool", tool="sleep",
                             input={"seconds": 0.05})
                        for i in range(1, n_steps + 1)
                    ],
                )
            ],
        )
    )
    job = await engine.run_job(journey.id, JobRunRequest(stage_id="stg"))
    assert job is not None

    # Sample statuses rapidly for the whole job lifetime.
    observed: list[JobStatus] = []
    deadline = asyncio.get_event_loop().time() + 3.0
    cancelled_once = False
    while asyncio.get_event_loop().time() < deadline:
        cur = (await engine.get_job(journey.id, job.id)).status
        observed.append(cur)
        if cur in TERMINAL:
            break
        if cancel_after_ms and not cancelled_once and len(observed) * 10 >= cancel_after_ms:
            await engine.cancel_job(journey.id, job.id)
            cancelled_once = True
        await asyncio.sleep(0.01)

    # Invariant: adjacent statuses obey the transition graph. `strict=False`
    # is intentional here: observed[1:] is N-1 items vs observed's N; zip
    # naturally truncates to the shorter.
    for prev, nxt in zip(observed, observed[1:], strict=False):
        assert nxt in ALLOWED_NEXT[prev], f"illegal transition {prev} -> {nxt}"

    # Terminal states are absorbing: once seen, never left.
    terminal_seen = False
    for s in observed:
        if s in TERMINAL:
            terminal_seen = True
        else:
            assert not terminal_seen, f"status {s} after terminal in {observed}"
