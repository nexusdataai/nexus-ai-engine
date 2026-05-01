"""MCP server exposing journey + logs/reports tools.

PORT FIDELITY CHECKLIST — do not simplify when porting.
Source:
    /opt/mycode/nexus/nexus-backend/src/tools/journey_tool.py
    /opt/mycode/nexus/nexus-backend/src/tools/logs_and_reports_tool.py

Tool schemas (action enums, request/response shapes) MUST match nexus-backend
1:1 so existing MCP clients work unchanged. Tool registration lands in phase 7
for logs_and_reports and phase 9 for journey_tool, aligning with the phases
that port the underlying services.
"""

from __future__ import annotations

from typing import Any, Optional


def create_mcp_server(engine: Optional[Any] = None):  # pragma: no cover - stub
    """Build the FastMCP server and register library-backed tools.

    Not implemented yet. Lands alongside the services in phases 7 and 9.
    """
    raise NotImplementedError(
        "create_mcp_server is a scaffold placeholder. "
        "Tool registration lands in phases 7 (logs/reports) and 9 (journey) of the extraction plan."
    )
