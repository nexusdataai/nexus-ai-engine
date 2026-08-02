"""Legacy BaseStage bridge for demo processors (docs/spec/020)."""

from __future__ import annotations

from typing import Any

from nexus_ai_engine.stages import get_stage_class


class LegacyStageAdapter:
    """Invoke a registered BaseStage demo processor as a synchronous tool."""

    def __init__(self, stage_id: str) -> None:
        self.stage_id = stage_id
        cls = get_stage_class(stage_id)
        if cls is None:
            raise ValueError(f"unknown stage: {stage_id}")
        self._stage_cls = cls

    async def run(self, *, journey_id: str = "legacy", job_id: str = "legacy") -> dict[str, Any]:
        stage = self._stage_cls(
            journey_id=journey_id,
            stage_id=self.stage_id,
            job_id=job_id,
        )
        # Demo stages expose process(); rc1 stub returns without full job context.
        if hasattr(stage, "process"):
            return {"stage_id": self.stage_id, "status": "legacy_ok"}
        return {"stage_id": self.stage_id, "status": "noop"}

    @staticmethod
    def is_registered(stage_id: str) -> bool:
        return get_stage_class(stage_id) is not None
