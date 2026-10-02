"""BaseStage contract, stage registry, and PluginJourneyStage.

Public surface the host application's stage classes (e.g. nexus-backend's 16
domain stages) consume:

- :class:`BaseStage` — the abstract base class to subclass
- :func:`register_stage`, :func:`get_stage_class`, :func:`list_available_stages`
  — registry hooks the host calls at startup
- :class:`PluginJourneyStage` — the dynamic YAML-driven stage
- :func:`register_demo_stages`, :data:`DEMO_JOURNEYS` — opt-in synthetic
  stages shipped with the library for performance / smoke testing of the
  standalone deploy. See :mod:`.demo`.
"""

from .base_stage import BaseStage
from .demo import (
    DEMO_JOURNEYS,
    DemoStage,
    list_demo_stage_ids,
    register_demo_stages,
)
from .job_archival import JobArchivalStage, register_job_archival_stage
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
    "DEMO_JOURNEYS",
    "DemoStage",
    "JobArchivalStage",
    "PluginJourneyStage",
    "STAGE_REGISTRY",
    "clear_registry",
    "get_stage_class",
    "list_available_stages",
    "list_demo_stage_ids",
    "register_demo_stages",
    "register_job_archival_stage",
    "register_stage",
]
