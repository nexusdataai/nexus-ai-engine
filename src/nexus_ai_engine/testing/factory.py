"""Factories that assemble an in-memory engine + app for tests."""

from __future__ import annotations

from typing import Any, Optional

from ..config import EngineConfig
from ..execution import InMemoryEngine


def make_test_engine(*, seed_demo: bool = True, **overrides: Any) -> InMemoryEngine:
    """Build an engine suitable for tests. Wraps :func:`build_engine`."""
    from ..factory import build_engine

    _ = EngineConfig(
        region="us-east-1",
        dynamodb_transformation_table="test-transformation",
        dynamodb_prompts_table="test-prompts",
        s3_journey_logs_bucket="test-logs",
        s3_journey_reports_bucket="test-reports",
        max_concurrent_jobs=overrides.pop("max_concurrent_jobs", 4),
        extras=overrides,
    )
    return build_engine(_, seed_demo=seed_demo)


def make_test_app(engine: Optional[Any] = None, *, seed_demo: bool = True):
    """Return a FastAPI app configured for in-process testing."""
    from ..server.app import create_app

    if engine is None:
        engine = make_test_engine(seed_demo=seed_demo)
    return create_app(engine=engine)


def make_test_mcp_server(engine: Optional[Any] = None):
    """Return an MCP server configured for in-process testing.

    Pre-phase-7 this raises ``NotImplementedError`` because the MCP server
    wiring lands with the journey/logs-reports tool activation.
    """
    from ..server.mcp import create_mcp_server

    if engine is None:
        engine = make_test_engine()
    return create_mcp_server(engine=engine)
