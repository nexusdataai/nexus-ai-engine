"""Single-tick entry point for Temporal activity shell (docs/spec/020)."""

from __future__ import annotations

from uuid import UUID

from nexus_ai_engine.executor.manager import ExecutionManager, TickOutcome


async def executor_tick(manager: ExecutionManager, execution_id: UUID) -> TickOutcome:
    return await manager.tick(execution_id)
