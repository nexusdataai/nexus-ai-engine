"""Runtime hooks the host application can inject for plugin journey execution.

Backend wires its ``VirtualQueryService`` (which depends on
``mapping_rule_models.VirtualQueryRequest`` / ``VirtualFilter``) and tool
registry through these helpers at startup; plugin journeys then resolve their
``query_virtual_entity`` calls and tool dispatch through them. Library-only
callers can leave the runtime unset and plugin journeys will fall back to
no-op responses for missing tools / queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class PluginRuntime:
    """Container for host-injected dependencies used by plugin journeys."""

    virtual_query_service: Any = None
    tool_registry: Optional[Dict[str, Any]] = None
    virtual_query_request_builder: Optional[Callable[..., Any]] = None
    extras: Dict[str, Any] = field(default_factory=dict)


_runtime: PluginRuntime = PluginRuntime()


def set_runtime(runtime: PluginRuntime) -> None:
    """Replace the process-wide plugin runtime."""
    global _runtime
    _runtime = runtime


def get_runtime() -> PluginRuntime:
    """Return the current plugin runtime (empty by default)."""
    return _runtime


def build_virtual_query_request(*, entity: str, filters: Any, limit: int = 500) -> Any:
    """Build a virtual-query request via the host-injected builder.

    Raises ``RuntimeError`` if no builder has been wired. Backend wires this
    via ``set_runtime(PluginRuntime(virtual_query_request_builder=...))``.
    """
    builder = _runtime.virtual_query_request_builder
    if builder is None:
        raise RuntimeError(
            "virtual_query_request_builder is not configured; "
            "the host application must call plugins.runtime.set_runtime(...)."
        )
    return builder(entity=entity, filters=filters, limit=limit)
