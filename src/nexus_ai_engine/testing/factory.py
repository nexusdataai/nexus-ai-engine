"""Factories that assemble an in-memory engine + app for tests."""

from __future__ import annotations

from typing import Any, Optional

from ..config import EngineConfig


def make_test_engine(**overrides: Any) -> Optional[Any]:
    """Build an engine suitable for tests.

    Returns ``None`` today because ``build_engine`` is a scaffold placeholder.
    Starting in phase 3 of the extraction plan this returns a fully-wired
    Engine with in-memory adapters by default. Test fixtures tolerate the
    ``None`` return and assert on 501 / 503 behavior meanwhile.
    """
    config = EngineConfig(
        region="us-east-1",
        dynamodb_transformation_table="test-transformation",
        dynamodb_prompts_table="test-prompts",
        s3_journey_logs_bucket="test-logs",
        s3_journey_reports_bucket="test-reports",
        max_concurrent_jobs=overrides.pop("max_concurrent_jobs", 4),
        extras=overrides,
    )

    try:
        from ..factory import build_engine

        return build_engine(config)
    except NotImplementedError:
        return None


def make_test_app(engine: Optional[Any] = None):
    """Return a FastAPI app configured for in-process testing.

    Creates an engine via :func:`make_test_engine` when none is supplied.
    """
    from ..server.app import create_app

    if engine is None:
        engine = make_test_engine()
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
