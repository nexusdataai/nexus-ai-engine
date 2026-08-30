"""FastAPI app factory for the Nexus AI Engine reference server.

The factory composes the routers that belong to the library: health/readiness,
journeys, jobs, logs, reports, prompts, schedules, and the embedded UI. Each
router is mounted under the same prefix nexus-backend uses today so UIs and
MCP clients work unchanged when a host app swaps its own journey/prompts
routes for the library's.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..execution import InMemoryEngine
from .routers import executions as executions_router
from .routers import fleet as fleet_router
from .routers import health as health_router
from .routers import jobs as jobs_router
from .routers import journey_dsl_api as journey_dsl_router
from .routers import journeys as journeys_router
from .routers import logs as logs_router
from .routers import prompts as prompts_router
from .routers import queue as queue_router
from .routers import reports as reports_router
from .routers import schedules as schedules_router
from .routers import stages_registry as stages_registry_router
from .routers import tool_packages as tool_packages_router
from .routers import ui as ui_router
from .routers import workers as workers_router
from .observability import build_metrics_registry

logger = logging.getLogger(__name__)

JOURNEYS_PREFIX = "/api/v1/journeys"
EXECUTIONS_PREFIX = "/api/v1/executions"
API_V1_PREFIX = "/api/v1"
PROMPTS_PREFIX = "/api/v1/prompts"
SCHEDULES_PREFIX = "/api/v1/schedules"


def _local_demo_seed_lifespan(engine: Optional[Any]):
    """On local + DynamoDB engine startup, seed demo journeys if the table is empty."""

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        from ..events.sse_manager import sse_manager
        from ..services.stale_job_manager import start_stale_job_sweeper

        sse_manager.enable_redis_bridge(publish_only=False)
        if engine is not None and hasattr(engine, "execution_runtime"):
            engine.execution_runtime.sse.enable_redis_bridge(publish_only=False)
        start_stale_job_sweeper()
        await sse_manager.start_cleanup_task()

        from ..factory import Engine

        if isinstance(engine, Engine) and engine.config.environment == "local":
            seed_on = os.environ.get("SEED_DEMO_JOURNEYS", "true").lower() not in (
                "0",
                "false",
                "no",
                "off",
            )
            if seed_on:
                from ..services.demo_seed import seed_demo_journeys_if_empty

                try:
                    created = await seed_demo_journeys_if_empty(engine.journeys)
                    if created:
                        logger.info("Seeded %d demo journeys for local persisted dev", created)
                except Exception:
                    logger.exception("Demo journey seed failed on startup")
        yield
        await sse_manager.stop_cleanup_task()

    return _lifespan


def create_app(engine: Optional[Any] = None, *, cors_origins: Optional[list[str]] = None) -> FastAPI:
    """Build the reference FastAPI app.

    Two router sets ship side-by-side. Which one is mounted depends on the
    engine kind passed in:

    - ``InMemoryEngine`` (or ``None``) — mount the slim canonical routers
      under ``nexus_ai_engine.server.routers.*``. They speak the
      ``InMemoryEngine`` method shape directly (``engine.run_job(...)``)
      and are what the embedded UI demo, the test harness, and the v2
      page exercise.
    - Production ``Engine`` facade (DynamoDB + S3 wired in by
      ``factory.build_engine`` when ``EngineConfig.dynamodb_transformation_table``
      is set) — mount the legacy routers under
      ``nexus_ai_engine.server.routers.legacy.*``. They wrap
      ``JourneyService`` / ``LogsAndReportsService`` / ``PromptsService`` /
      ``SchedulerService`` and were originally written for ``nexus-backend``.
      The slim routers cannot consume the production ``Engine`` shape.

    Both router sets sit at the same ``/api/v1/*`` prefixes, so the embedded
    UI and external HTTP/MCP clients work unchanged across modes.

    Args:
        engine: An ``Engine`` or ``InMemoryEngine`` instance produced by
            ``nexus_ai_engine.factory.build_engine``. When ``None``, routes
            that require services will return 503. Tests typically use
            ``nexus_ai_engine.testing.make_test_app`` which wires a
            pre-seeded in-memory engine.
        cors_origins: Optional list of allowed CORS origins. None disables CORS.
    """
    app = FastAPI(
        title="Nexus AI Engine",
        version=__version__,
        description=(
            "Journey/stage/job orchestration engine. Reference server exposing the "
            "canonical HTTP surface ported from nexus-backend plus an embedded "
            "React UI for testing journeys, jobs, schedules, and prompts."
        ),
        lifespan=_local_demo_seed_lifespan(engine),
    )

    app.state.engine = engine
    app.state.metrics_registry = build_metrics_registry()

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # System routers — always mounted regardless of engine kind. The
    # stages-registry router is a read-only window onto STAGE_REGISTRY
    # and is needed by the v2 UI to enrich `journey.stages[].steps` (the
    # legacy DynamoDB router doesn't persist step lists; steps come from
    # the registered stage class at run time).
    app.include_router(health_router.router, tags=["health"])
    app.include_router(ui_router.router, tags=["ui"])
    app.include_router(stages_registry_router.router, tags=["stages"])
    app.include_router(fleet_router.router, prefix=API_V1_PREFIX, tags=["fleet"])
    app.include_router(queue_router.router, prefix=API_V1_PREFIX, tags=["queue"])
    app.include_router(workers_router.router, prefix=API_V1_PREFIX, tags=["workers"])

    # Engine surface — branch on engine kind. The InMemoryEngine path is the
    # default (no DynamoDB config supplied); the production path activates
    # automatically when ``factory.build_engine`` returns the ``Engine``
    # facade (i.e. when DynamoDB + S3 names are present in EngineConfig).
    if engine is None or isinstance(engine, InMemoryEngine):
        app.include_router(journey_dsl_router.router, prefix=JOURNEYS_PREFIX, tags=["journey-dsl"])
        app.include_router(journeys_router.router, prefix=JOURNEYS_PREFIX, tags=["journeys"])
        app.include_router(executions_router.router, prefix=EXECUTIONS_PREFIX, tags=["executions"])
        app.include_router(tool_packages_router.router, prefix=API_V1_PREFIX, tags=["tools"])
        app.include_router(jobs_router.router,     prefix=JOURNEYS_PREFIX, tags=["jobs"])
        app.include_router(logs_router.router,     prefix=JOURNEYS_PREFIX, tags=["logs"])
        app.include_router(reports_router.router,  prefix=JOURNEYS_PREFIX, tags=["reports"])
        app.include_router(prompts_router.router,  prefix=PROMPTS_PREFIX,  tags=["prompts"])
        app.include_router(schedules_router.router, prefix=SCHEDULES_PREFIX, tags=["schedules"])
        logger.info("Mounted slim routers (InMemoryEngine mode)")
    else:
        # Production path — mount the legacy routers that talk to the real
        # services. Imported lazily so the in-memory dev path stays free of
        # boto3/JourneyService construction at import time.
        from .routers.legacy import journey_api as legacy_journey
        from .routers.legacy import prompts_api as legacy_prompts
        from .routers.legacy import schedule_api as legacy_schedule

        # ``legacy/journey_api`` exposes ``router = APIRouter()`` (no
        # built-in prefix), so we mount under the canonical prefix. It also
        # absorbs jobs + logs + reports + aggregate-report + stream URLs
        # (everything under /api/v1/journeys/*) — see endpoint listing in
        # legacy/journey_api.py for the full surface.
        # Mount DSL routes before legacy ``/{journey_id}`` catch-alls so paths
        # like ``/api/v1/journeys/dsl`` are not treated as journey IDs.
        app.include_router(journey_dsl_router.router, prefix=JOURNEYS_PREFIX, tags=["journey-dsl"])
        app.include_router(legacy_journey.router, prefix=JOURNEYS_PREFIX, tags=["journeys"])
        app.include_router(executions_router.router, prefix=EXECUTIONS_PREFIX, tags=["executions"])
        app.include_router(tool_packages_router.router, prefix=API_V1_PREFIX, tags=["tools"])
        # ``legacy/prompts_api`` already declares prefix="/api/v1/prompts"
        # in its own APIRouter constructor, so mount at root.
        app.include_router(legacy_prompts.router, tags=["prompts"])
        app.include_router(legacy_schedule.router, prefix=SCHEDULES_PREFIX, tags=["schedules"])

        # Expose the production services on app.state so any future
        # request-scoped dependency that wants to reach them (or tests
        # that want to introspect) can pick them up. The legacy routers
        # themselves construct module-level singletons via
        # ``JourneyService()`` / ``get_prompts_service()`` /
        # ``SchedulerService.get_instance()`` which read ``get_config()``.
        app.state.journey_service       = engine.journeys
        app.state.prompts_service       = engine.prompts
        app.state.scheduler_service     = engine.schedules
        app.state.logs_reports_service  = engine.logs_and_reports
        app.state.job_executor          = engine.job_executor
        app.state.execution_runtime     = engine.execution_runtime
        app.state.dsl_store             = engine.dsl_store
        logger.info("Mounted legacy routers (production Engine mode)")

    # Static assets for the embedded UI — shared across both modes.
    ui_router.mount_ui(app)

    logger.info("Nexus AI Engine reference server app created (version %s)", __version__)
    return app
