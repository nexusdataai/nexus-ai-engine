"""BaseStage contract, stage registry, and PluginJourneyStage.

Public surface the host application's stage classes (e.g. nexus-backend's 16
domain stages) consume:

- :class:`BaseStage` — the abstract base class to subclass
- :func:`register_stage`, :func:`get_stage_class`, :func:`list_available_stages`
  — registry hooks the host calls at startup
- :class:`PluginJourneyStage` — the dynamic YAML-driven stage
"""

from .base_stage import BaseStage
from .plugin_journey_stage import PluginJourneyStage
from .registry import (
    STAGE_REGISTRY,
    clear_registry,
    get_stage_class,
    list_available_stages,
    register_stage,
)

__all__ = [
    "BaseStage",
    "PluginJourneyStage",
    "STAGE_REGISTRY",
    "clear_registry",
    "get_stage_class",
    "list_available_stages",
    "register_stage",
]
