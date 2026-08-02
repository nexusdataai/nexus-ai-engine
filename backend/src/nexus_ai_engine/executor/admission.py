"""Admission control for concurrent executions (spec 030)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from nexus_ai_engine.config import get_config


class AdmissionRejectedError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class AdmissionController:
    """Global and per-journey concurrency gates."""

    repository: object | None = None

    async def admit(self, *, journey_id: str, journey_max_parallel: int | None = None) -> None:
        config = get_config()
        global_max = config.max_concurrent_jobs
        if self.repository is None:
            return

        running = await self.repository.get_running_count()
        if running >= global_max:
            raise AdmissionRejectedError(f"global limit {global_max} reached")

        if journey_max_parallel is not None:
            journey_running = await self.repository.count_running_for_journey(journey_id)
            if journey_running >= journey_max_parallel:
                raise AdmissionRejectedError(
                    f"journey {journey_id} limit {journey_max_parallel} reached"
                )

    async def on_started(self, execution_id: UUID) -> None:
        if self.repository is not None:
            await self.repository.increment_running()

    async def on_terminal(self, execution_id: UUID) -> None:
        if self.repository is not None:
            await self.repository.decrement_running()
