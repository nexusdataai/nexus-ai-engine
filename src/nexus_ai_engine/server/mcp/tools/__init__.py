"""MCP tool registrars ported from nexus-backend.

Two MCP tools ship with the library:

- :func:`register_journey_tools` — adds the canonical ``journeys_tool``
  (full journey/stage/rule/job CRUD).
- :func:`register_logs_and_reports_tools` — adds the canonical
  ``logs_and_reports_tool`` (log retrieval, search, report generation,
  performance + error analysis).

Host applications import these in their MCP server bootstrap and call them
with their existing ``FastMCP`` instance — backend's ``src/server.py`` does
exactly that.
"""

from .journey_tool import register_journey_tools
from .logs_and_reports_tool import register_logs_and_reports_tools

__all__ = ["register_journey_tools", "register_logs_and_reports_tools"]
