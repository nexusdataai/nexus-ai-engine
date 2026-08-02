"""Backend-compatible (legacy) routers.

These match the exact endpoint shapes nexus-backend's ``src/apis/`` exposed
today (camelCase fields, ``{success, message, data}`` envelopes, etc.) so
existing UIs and MCP clients keep working unchanged when the host mounts
them under their canonical prefixes:

- :mod:`.journey_api` mounted at ``/api/v1/journeys``
- :mod:`.prompts_api`  mounted at ``/api/v1/prompts``
- :mod:`.schedule_api` mounted at ``/api/v1/schedules``

The library's slim canonical routers under :mod:`nexus_ai_engine.server.routers`
remain available for the in-memory engine reference UI / fresh consumers.
"""

from . import journey_api, prompts_api, schedule_api

__all__ = ["journey_api", "prompts_api", "schedule_api"]
