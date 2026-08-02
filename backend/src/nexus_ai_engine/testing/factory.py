"""Factories that assemble an in-memory engine + app for tests."""

from __future__ import annotations

from typing import Any, Optional

from ..config import EngineConfig
from ..execution import InMemoryEngine


def make_test_engine(*, seed_demo: bool = True, **overrides: Any) -> InMemoryEngine:
    """Build an in-memory engine suitable for tests.

    Tests always get the in-memory engine — the harness predates the
    DynamoDB-backed services and exercises the canonical service contract
    in isolation. Pass ``in_memory=True`` to :func:`build_engine` directly
    if you want explicit control.
    """
    from ..factory import build_engine

    return build_engine(in_memory=True, seed_demo=seed_demo)


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
