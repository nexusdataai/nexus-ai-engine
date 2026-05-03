"""behave environment — spins up the in-process harness for all scenarios.

Each scenario gets ``context.app`` (the FastAPI app), ``context.base_url``
(``http://testserver``), and ``context.client`` (an httpx.AsyncClient bound
to the ASGI transport).
"""

from __future__ import annotations

import asyncio

from nexus_ai_engine.testing import TestHttpClient, make_test_app, make_test_engine
from tests.fixtures.steps import register_all


def before_all(context):
    # Create an engine with the deterministic step tools registered so
    # BDD scenarios that declare `type: tool` on their steps get the
    # deterministic dispatch path. Seeded demo journeys are unaffected.
    engine = make_test_engine()
    register_all(engine)
    context.engine = engine
    context.app = make_test_app(engine=engine)
    context.base_url = "http://testserver"
    context.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(context.loop)
    context._client_cm = TestHttpClient(context.app, base_url=context.base_url)
    context.client = context.loop.run_until_complete(context._client_cm.__aenter__())


def before_scenario(context, scenario):
    """Per-scenario state bag used by shared step definitions."""
    context.last_body = None
    context.journey_id = None
    context.job_id = None


def after_all(context):
    if hasattr(context, "_client_cm"):
        context.loop.run_until_complete(context._client_cm.__aexit__(None, None, None))
    if hasattr(context, "loop"):
        context.loop.close()
