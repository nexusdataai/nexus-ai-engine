"""Endurance-tier fixtures — concurrency helpers for load smoke tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.testing import make_test_engine
from tests.fixtures.steps import register_all


@pytest.fixture
def gather_n() -> Callable[[int, Callable[[], Awaitable[Any]]], Awaitable[list[Any]]]:
    """Return an awaitable that runs ``coro_factory()`` ``n`` times concurrently."""

    async def _gather(n: int, coro_factory: Callable[[], Awaitable[Any]]) -> list[Any]:
        return await asyncio.gather(*[coro_factory() for _ in range(n)])

    return _gather


@pytest.fixture
def engine() -> InMemoryEngine:
    """Override the harness `engine` so endurance tests see deterministic
    tools. Seeded demo journeys keep running via the random simulator
    because they don't declare `type: tool`.
    """
    e = make_test_engine()
    register_all(e)
    return e


async def wait_for_terminal(engine: InMemoryEngine, journey_id: str, job_id: str, *, timeout: float = 15.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        job = await engine.get_job(journey_id, job_id)
        if job and job.status.value in ("completed", "failed", "cancelled"):
            return
        await asyncio.sleep(0.02)
    job = await engine.get_job(journey_id, job_id)
    status = job.status.value if job else "missing"
    raise AssertionError(f"job {job_id} did not terminate within {timeout}s (status={status})")
