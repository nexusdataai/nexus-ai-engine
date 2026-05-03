"""E2E-tier fixtures — in-process FastAPI harness.

All route-exercising tests share the ``app`` + ``http_client`` fixtures from
the harness plugin (``nexus_ai_engine.testing.fixtures``). This file is kept
for tier-local extensions.
"""

from __future__ import annotations

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.testing import make_test_engine
from tests.fixtures.steps import register_all


@pytest.fixture
def engine() -> InMemoryEngine:
    """Override the harness `engine` fixture so every e2e test's engine
    has the deterministic step tools registered. The 5 seeded demo
    journeys don't declare ``type: tool``, so they keep running via the
    random simulator; new e2e tests that POST a journey with
    ``type: tool`` steps get the deterministic dispatch path.
    """
    e = make_test_engine()
    register_all(e)
    return e
