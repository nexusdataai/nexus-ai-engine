"""Stage Registry for the AI Engine.

Holds the mapping ``stage_id -> BaseStage subclass`` shared across the
process. The host application is expected to populate the registry at
startup by importing its concrete stage classes and calling
``register_stage("...", MyStage)``.

Looking up an unknown stage falls back to ``PluginJourneyStage`` so
journeys defined entirely in YAML continue to work without explicit
registration.
"""

from __future__ import annotations

from typing import Dict, List, Type

from .base_stage import BaseStage

STAGE_REGISTRY: Dict[str, Type[BaseStage]] = {}


def register_stage(stage_id: str, stage_class: Type[BaseStage]) -> None:
    """Register a stage implementation under ``stage_id``.

    Raises:
        TypeError: If ``stage_class`` does not inherit from ``BaseStage``.
    """
    if not isinstance(stage_class, type) or not issubclass(stage_class, BaseStage):
        raise TypeError(
            f"Stage class {stage_class!r} must inherit from BaseStage"
        )
    STAGE_REGISTRY[stage_id] = stage_class


def get_stage_class(stage_id: str) -> Type[BaseStage]:
    """Return the registered stage class.

    Falls back to :class:`PluginJourneyStage` (loaded lazily to avoid
    circular imports) when the id is unknown — this matches nexus-backend's
    behavior so YAML-only plugin journeys keep working.
    """
    cls = STAGE_REGISTRY.get(stage_id)
    if cls is not None:
        return cls
    try:
        from .plugin_journey_stage import PluginJourneyStage
        return PluginJourneyStage
    except ImportError as exc:
        raise ValueError(
            f"Unknown stage ID: {stage_id}. "
            f"Available stages: {', '.join(STAGE_REGISTRY.keys())}"
        ) from exc


def list_available_stages() -> List[str]:
    """Return all registered stage ids."""
    return list(STAGE_REGISTRY.keys())


def clear_registry() -> None:
    """Remove all registered stages (test helper)."""
    STAGE_REGISTRY.clear()
