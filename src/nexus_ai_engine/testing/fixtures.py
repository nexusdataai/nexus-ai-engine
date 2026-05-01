"""Pytest fixtures provided by the nexus-ai-engine harness.

Registered as a pytest plugin via the ``pytest11`` entry point in
``pyproject.toml``; anyone installing ``nexus-ai-engine[harness]`` gets these
fixtures automatically.

Fixtures:
    engine_config     EngineConfig with sane test defaults
    engine            Engine instance (None pre-phase-3)
    app               FastAPI app wired with the test engine
    http_client       Async httpx client bound to the in-process app
    mcp_client        In-process MCP client (pre-phase-7 raises on use)
    journey_runner    JourneyYAMLRunner bound to the test app
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest
import pytest_asyncio

from ..config import EngineConfig
from .clients import TestHttpClient, TestMCPClient
from .factory import make_test_app, make_test_engine, make_test_mcp_server
from .journeys import JourneyYAMLRunner


@pytest.fixture
def engine_config() -> EngineConfig:
    return EngineConfig(
        region="us-east-1",
        dynamodb_transformation_table="test-transformation",
        dynamodb_prompts_table="test-prompts",
        s3_journey_logs_bucket="test-logs",
        s3_journey_reports_bucket="test-reports",
        max_concurrent_jobs=4,
    )


@pytest.fixture
def engine(engine_config: EngineConfig) -> Any:
    return make_test_engine()


@pytest.fixture
def app(engine: Any):
    return make_test_app(engine=engine)


@pytest_asyncio.fixture
async def http_client(app: Any) -> AsyncIterator[Any]:
    async with TestHttpClient(app) as client:
        yield client


@pytest.fixture
def mcp_client(engine: Any) -> TestMCPClient:
    try:
        server = make_test_mcp_server(engine=engine)
    except NotImplementedError:
        server = None
    return TestMCPClient(mcp_server=server)


@pytest.fixture
def journey_runner(app: Any) -> JourneyYAMLRunner:
    return JourneyYAMLRunner(app=app)
