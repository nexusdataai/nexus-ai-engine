"""Integration-tier fixtures.

These tests treat the InMemoryEngine as the integration target: real CRUD
flows, real asyncio concurrency, deterministic step tools registered on
the engine so assertions are stable.

Moto-backed DynamoDB / S3 tests live under the same directory and
activate once the adapter modules land (deferred in the plan).
"""

from __future__ import annotations

import asyncio

import pytest

from nexus_ai_engine.execution import InMemoryEngine, seed
from tests.fixtures.steps import register_all


@pytest.fixture
def engine() -> InMemoryEngine:
    """Fresh in-memory engine, no seeded journeys, with all deterministic
    step tools registered.
    """
    e = InMemoryEngine()
    register_all(e)
    return e


@pytest.fixture
def seeded_engine() -> InMemoryEngine:
    """Engine with the 5 demo journeys seeded AND all deterministic tools
    registered. The seeded journeys themselves don't declare `type: tool`
    so they continue to use the random simulator.
    """
    e = InMemoryEngine()
    seed(e)
    register_all(e)
    return e


async def wait_for_terminal(engine: InMemoryEngine, journey_id: str, job_id: str, *, timeout: float = 10.0) -> None:
    """Block until the job reaches a terminal status or timeout expires.

    Raises AssertionError on timeout so tests fail loud instead of hanging.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        job = await engine.get_job(journey_id, job_id)
        if job and job.status.value in ("completed", "failed", "cancelled"):
            return
        await asyncio.sleep(0.02)
    job = await engine.get_job(journey_id, job_id)
    status = job.status.value if job else "missing"
    raise AssertionError(f"job {job_id} did not reach terminal within {timeout}s (status={status})")
