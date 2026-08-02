"""System-level read-only view of the stage registry.

Exposes ``GET /api/v1/stages/registered`` which returns every stage
currently in :data:`nexus_ai_engine.stages.STAGE_REGISTRY` together
with its name, description, and step list. Used by the v2 UI to enrich
``journey.stages`` records when the persisting backend (legacy DynamoDB
router) drops the per-stage step list.

Stage step lists are an inherent property of the registered class
(``stage.steps`` is read by ``TransformationJobExecutor`` at run time),
not of the journey row in DynamoDB. Surfacing them here lets the UI
render the stepper without a per-stage HTTP round-trip and without
having to persist the steps redundantly.

Always-on regardless of which engine kind is wired (slim or legacy),
because the registry is process-global.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ...stages import STAGE_REGISTRY, DemoStage

logger = logging.getLogger(__name__)

router = APIRouter()


def _introspect_stage_class(stage_id: str, cls: type) -> Dict[str, Any]:
    """Pull a stage's metadata without running its full ``__init__``.

    ``BaseStage.__init__`` constructs DynamoDB + S3 boto3 clients eagerly
    (it expects the engine config singleton to point at a real table).
    Calling it from this introspection path would fail when the engine
    isn't wired (tests, ``--engine None`` smoke runs) and would needlessly
    open AWS clients in production every time the v2 UI hits this route.

    Strategy:

    1. ``DemoStage`` subclasses expose their canonical step list as the
       class-level ``STEP_DEFINITIONS`` attribute. Read it directly — no
       instance needed.
    2. Other ``BaseStage`` subclasses (host-registered domain stages)
       expect to be instantiated. Try with ``enable_logging=False`` and
       fall back to the positional signature; on any failure return a
       minimal record so a single broken stage class doesn't break the
       whole registry endpoint.
    """
    if isinstance(cls, type) and issubclass(cls, DemoStage):
        return {
            "stage_id":    stage_id,
            "name":        getattr(cls, "STAGE_NAME", stage_id),
            "description": getattr(cls, "STAGE_DESCRIPTION", ""),
            "steps":       [
                {"id": s["id"], "name": s["name"],
                 "description": s.get("description", "")}
                for s in getattr(cls, "STEP_DEFINITIONS", [])
            ],
        }

    try:
        try:
            instance = cls("introspect", stage_id, "introspect",
                           None, None, enable_logging=False)
        except TypeError:
            instance = cls("introspect", stage_id, "introspect", None, None)
        return {
            "stage_id":    stage_id,
            "name":        getattr(instance, "stage_name", stage_id),
            "description": getattr(instance, "stage_description", ""),
            "steps":       list(getattr(instance, "steps", [])),
        }
    except Exception as exc:
        logger.warning(
            "Stage introspection for %s failed: %s — returning minimal record",
            stage_id, exc,
        )
        return {
            "stage_id":    stage_id,
            "name":        stage_id,
            "description": "",
            "steps":       [],
            "error":       str(exc),
        }


@router.get("/api/v1/stages/registered")
async def list_registered_stages() -> Dict[str, Any]:
    """Return every stage in STAGE_REGISTRY with its name + step list."""
    stages: List[Dict[str, Any]] = []
    for stage_id in sorted(STAGE_REGISTRY):
        stages.append(_introspect_stage_class(stage_id, STAGE_REGISTRY[stage_id]))
    return {
        "count":  len(stages),
        "stages": stages,
    }


@router.get("/api/v1/stages/registered/{stage_id}")
async def get_registered_stage(stage_id: str) -> Dict[str, Any]:
    """Return one stage's metadata, or 404 if the stage isn't registered.

    Falls back through ``get_stage_class`` so YAML-driven plugin
    journeys (resolved via :class:`PluginJourneyStage`) get a sensible
    record even though they're not in :data:`STAGE_REGISTRY` directly.
    """
    cls = STAGE_REGISTRY.get(stage_id)
    if cls is None:
        # PluginJourneyStage fallback would silently succeed here too, but
        # that's actively misleading for callers polling for "is this
        # stage runnable?". 404 keeps the contract honest.
        raise HTTPException(status_code=404, detail=f"Stage {stage_id} not registered")
    return _introspect_stage_class(stage_id, cls)
