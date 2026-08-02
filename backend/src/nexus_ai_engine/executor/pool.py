"""Asyncio execution pool — dev/staging fallback when Temporal is unavailable."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class AsyncioExecutionPool:
    """Runs execution tick loops with a concurrency semaphore."""

    runtime: object
    max_concurrent: int = 20
    _sem: asyncio.Semaphore = field(init=False)
    _tasks: set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._sem = asyncio.Semaphore(self.max_concurrent)

    def submit(self, execution_id: UUID) -> None:
        task = asyncio.create_task(self._run(execution_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, execution_id: UUID) -> None:
        async with self._sem:
            await self.runtime.run_to_completion(execution_id)

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
