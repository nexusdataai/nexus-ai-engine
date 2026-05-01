"""FastAPI app factory for the Nexus AI Engine reference server.

The factory composes the routers that belong to the library: health/readiness,
journeys, jobs, logs, reports, prompts. Each router is mounted under the same
prefix nexus-backend uses today so UIs and MCP clients work unchanged when a
host app swaps its own journey/prompts routes for the library's.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .routers import health as health_router
from .routers import jobs as jobs_router
from .routers import journeys as journeys_router
from .routers import logs as logs_router
from .routers import prompts as prompts_router
from .routers import reports as reports_router

logger = logging.getLogger(__name__)

JOURNEYS_PREFIX = "/api/v1/journeys"
PROMPTS_PREFIX = "/api/v1/prompts"


def create_app(engine: Optional[Any] = None, *, cors_origins: Optional[list[str]] = None) -> FastAPI:
    """Build the reference FastAPI app.

    Args:
        engine: An ``Engine`` instance produced by ``nexus_ai_engine.factory.build_engine``.
            When ``None``, routes that require services will return 503
            (configuration missing). For tests, use
            ``nexus_ai_engine.testing.make_test_app`` which wires an in-memory
            engine automatically.
        cors_origins: Optional list of allowed CORS origins. None disables CORS.

    Returns:
        A configured ``FastAPI`` instance. The caller is responsible for
        running it (``uvicorn``, test client, etc.).
    """
    app = FastAPI(
        title="Nexus AI Engine",
        version=__version__,
        description=(
            "Journey/stage/job orchestration engine. Reference server exposing the "
            "canonical HTTP surface ported from nexus-backend."
        ),
    )

    app.state.engine = engine

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router.router, tags=["health"])
    app.include_router(journeys_router.router, prefix=JOURNEYS_PREFIX, tags=["journeys"])
    app.include_router(jobs_router.router, prefix=JOURNEYS_PREFIX, tags=["jobs"])
    app.include_router(logs_router.router, prefix=JOURNEYS_PREFIX, tags=["logs"])
    app.include_router(reports_router.router, prefix=JOURNEYS_PREFIX, tags=["reports"])
    app.include_router(prompts_router.router, prefix=PROMPTS_PREFIX, tags=["prompts"])

    logger.info("Nexus AI Engine reference server app created (version %s)", __version__)
    return app
