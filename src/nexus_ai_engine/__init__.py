"""Nexus AI Engine — journey/stage/job orchestration core.

Public surface (stable for 0.1.0a2):

- :class:`~nexus_ai_engine.config.EngineConfig` and
  :func:`~nexus_ai_engine.config.set_config` / :func:`get_config` — host
  application wires its AWS topology here at startup.
- :func:`~nexus_ai_engine.factory.build_engine` — composition root.
- :class:`~nexus_ai_engine.stages.BaseStage`, :func:`register_stage`,
  :func:`get_stage_class`, :func:`list_available_stages`,
  :class:`PluginJourneyStage` — stage authoring + registry.
- :mod:`nexus_ai_engine.services` — JourneyService, PromptsService,
  SchedulerService, LogsAndReportsService.
- :mod:`nexus_ai_engine.models` — every Pydantic shape (canonical + the
  legacy MCP / API envelopes ported from nexus-backend).
- :mod:`nexus_ai_engine.adapters.aws` — AWSClientManager + LocalStack
  helpers.
- :mod:`nexus_ai_engine.adapters.dynamodb` — ComprehensiveJourneyManager.
- :mod:`nexus_ai_engine.execution` — TransformationJobExecutor +
  InMemoryEngine.
- :mod:`nexus_ai_engine.events` — SSEManager + emit helpers.
"""

__version__ = "0.1.0a2"

from .config import EngineConfig, get_config, set_config
from .factory import Engine, build_engine

__all__ = [
    "Engine",
    "EngineConfig",
    "__version__",
    "build_engine",
    "get_config",
    "set_config",
]
