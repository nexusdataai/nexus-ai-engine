"""Shipped testing harness for nexus-ai-engine.

Public API:
    make_test_engine(**overrides) -> Engine | None
    make_test_app(engine=None) -> FastAPI
    make_test_mcp_server(engine=None)
    TestHttpClient
    TestMCPClient
    JourneyYAMLRunner, JourneyRunResult

Install with the harness extra:
    pip install "nexus-ai-engine[harness]"

Any project using pytest automatically receives the fixtures registered by
``nexus_ai_engine.testing.fixtures`` (via the pytest11 entry point). See
tests/README.md for usage patterns.
"""

from __future__ import annotations

from .clients import TestHttpClient, TestMCPClient
from .factory import make_test_app, make_test_engine, make_test_mcp_server
from .journeys import JourneyRunResult, JourneyYAMLRunner

__all__ = [
    "JourneyRunResult",
    "JourneyYAMLRunner",
    "TestHttpClient",
    "TestMCPClient",
    "make_test_app",
    "make_test_engine",
    "make_test_mcp_server",
]
