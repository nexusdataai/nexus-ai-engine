"""behave environment — spins up the in-process harness for all scenarios.

Each scenario gets ``context.app`` (the FastAPI app), ``context.base_url``
(``http://testserver``), and ``context.client`` (an httpx.AsyncClient bound
to the ASGI transport).
"""

from __future__ import annotations

import asyncio

from nexus_ai_engine.testing import TestHttpClient, make_test_app


def before_all(context):
    context.app = make_test_app()
    context.base_url = "http://testserver"
    context.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(context.loop)
    context._client_cm = TestHttpClient(context.app, base_url=context.base_url)
    context.client = context.loop.run_until_complete(context._client_cm.__aenter__())


def after_all(context):
    if hasattr(context, "_client_cm"):
        context.loop.run_until_complete(context._client_cm.__aexit__(None, None, None))
    if hasattr(context, "loop"):
        context.loop.close()
