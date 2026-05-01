"""Endurance-tier fixtures — concurrency helpers for load smoke tests."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

import pytest


@pytest.fixture
def gather_n() -> Callable[[int, Callable[[], Awaitable[Any]]], Awaitable[list[Any]]]:
    """Return an awaitable that runs ``coro_factory()`` ``n`` times concurrently."""

    async def _gather(n: int, coro_factory: Callable[[], Awaitable[Any]]) -> list[Any]:
        return await asyncio.gather(*[coro_factory() for _ in range(n)])

    return _gather
