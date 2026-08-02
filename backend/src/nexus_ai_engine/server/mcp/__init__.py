"""MCP server scaffolding + tool registrars.

The library exposes the canonical tool registrars
(:func:`register_journey_tools`, :func:`register_logs_and_reports_tools`)
so any host MCP server can mount them directly. nexus-backend's
``src/server.py`` does this in its FastMCP bootstrap.

A ``create_mcp_server`` convenience factory is also available for callers
that want a complete library-managed FastMCP server with both tools
pre-registered.
"""

from __future__ import annotations

from typing import Any, Optional

from .tools import register_journey_tools, register_logs_and_reports_tools, register_execution_tools


def create_mcp_server(engine: Optional[Any] = None, *, name: str = "nexus-ai-engine"):
    """Build a :class:`FastMCP` server with both engine tools pre-registered.

    Args:
        engine: Optional ``Engine`` facade from
            :func:`nexus_ai_engine.factory.build_engine`. Currently unused
            (the tools instantiate their own service singletons via the
            wired :func:`nexus_ai_engine.config.get_config`); reserved for
            future explicit engine injection.
        name: MCP server name (defaults to ``nexus-ai-engine``).
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(name)
    register_journey_tools(mcp)
    register_logs_and_reports_tools(mcp)
    runtime = getattr(engine, "execution_runtime", None) if engine is not None else None
    dsl_store = getattr(engine, "dsl_store", None) if engine is not None else None
    register_execution_tools(mcp, runtime=runtime, dsl_store=dsl_store)
    return mcp


__all__ = [
    "create_mcp_server",
    "register_journey_tools",
    "register_logs_and_reports_tools",
    "register_execution_tools",
]
