"""Composition root for the Nexus AI Engine.

Two engine flavors ship side-by-side:

- The **DynamoDB-backed engine** (default in production): a small
  :class:`Engine` facade exposing the four ported services (journeys,
  prompts, scheduler, logs+reports), the stage registry, and the SSE
  manager. ``build_engine(EngineConfig)`` wires the host's config into the
  process-wide singleton via :func:`nexus_ai_engine.config.set_config` so
  every service module picks up the right table / bucket names.
- The **in-memory engine** (used by the embedded UI demo, tests, and
  ``[harness]`` consumers): :class:`InMemoryEngine` from
  :mod:`nexus_ai_engine.execution.in_memory_engine`. Pass ``in_memory=True``
  (or omit ``EngineConfig`` entirely) to get one pre-seeded with demo data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .config import EngineConfig, set_config
from .execution import InMemoryEngine, seed
from .stages import (
    STAGE_REGISTRY,
    get_stage_class,
    list_available_stages,
    register_stage,
)


@dataclass
class Engine:
    """Facade returned by :func:`build_engine` when given an ``EngineConfig``.

    Holds singleton instances of the four production services plus a
    handle to the shared stage registry. Routers, MCP tools, and host
    application code grab services off this facade rather than constructing
    them directly so the wiring (table names, AWS credentials) stays in one
    place.

    ``stage_registry`` is the module-level :data:`STAGE_REGISTRY` dict
    exposed for ergonomics; the host calls ``engine.register_stage(id, cls)``
    at startup for each domain stage.
    """

    config: EngineConfig
    journeys: "JourneyService"
    prompts: "PromptsService"
    schedules: "SchedulerService"
    logs_and_reports: "LogsAndReportsService"
    job_executor: "TransformationJobExecutor"
    execution_runtime: "ExecutionRuntimeService"
    dsl_store: "DslJourneyStore"
    artifacts: "S3ArtifactStore"

    @property
    def stage_registry(self) -> dict:
        return STAGE_REGISTRY

    @staticmethod
    def register_stage(stage_id: str, stage_class: type) -> None:
        register_stage(stage_id, stage_class)

    @staticmethod
    def get_stage_class(stage_id: str) -> type:
        return get_stage_class(stage_id)

    @staticmethod
    def list_available_stages() -> list:
        return list_available_stages()


def build_engine(
    config: Optional[EngineConfig] = None,
    *,
    in_memory: bool = False,
    seed_demo: bool = True,
) -> Union[Engine, InMemoryEngine]:
    """Assemble and return the engine.

    Args:
        config: ``EngineConfig`` describing the host's AWS topology. When
            provided (and ``in_memory`` is False), wires the DynamoDB-backed
            services and returns an :class:`Engine` facade.
        in_memory: Force the in-memory engine even if ``config`` is given
            (useful for tests). When True, ``config`` is ignored.
        seed_demo: For the in-memory engine only — populate the demo set.
    """
    # In-memory path is taken when:
    # - explicitly requested via ``in_memory=True``, or
    # - no config given, or
    # - the config has no DynamoDB topology configured (callers that pass an
    #   empty ``EngineConfig()`` are doing local/test setup; the real
    #   DynamoDB-backed services need a transformation table at minimum).
    if in_memory or config is None or config.dynamodb_transformation_table is None or config.dynamodb_executions_table is None:
        engine = InMemoryEngine()
        if seed_demo:
            seed(engine)
        return engine

    # Wire the config into the process-wide singleton FIRST so every service
    # constructor (which calls ``get_config()`` internally) picks it up.
    set_config(config)

    # Imports are deferred to keep the in-memory path free of boto3 weight.
    from .adapters.dynamodb.execution_repo import DynamoDBExecutionRepository
    from .adapters.s3.artifact_store import S3ArtifactStore
    from .execution.runtime_service import ExecutionRuntimeService
    from .executor.admission import AdmissionController
    from .journeys.service import DslJourneyStore
    from .execution.transformation_job_executor import TransformationJobExecutor
    from .services import (
        JourneyService,
        LogsAndReportsService,
        PromptsService,
        SchedulerService,
    )

    repo = DynamoDBExecutionRepository()
    runtime = ExecutionRuntimeService(
        repository=repo,
        admission=AdmissionController(repository=repo),
    )

    return Engine(
        config=config,
        journeys=JourneyService(),
        prompts=PromptsService(),
        schedules=SchedulerService.get_instance(),
        logs_and_reports=LogsAndReportsService(),
        job_executor=TransformationJobExecutor(
            region_name=config.region, role_arn=config.role_arn
        ),
        execution_runtime=runtime,
        dsl_store=DslJourneyStore(),
        artifacts=S3ArtifactStore(),
    )
