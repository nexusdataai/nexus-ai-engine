"""Load Tool subclasses from package manifest module paths."""

from __future__ import annotations

import importlib

from nexus_ai_engine.tools.base.tool import Tool


class ToolLoadError(ValueError):
    """Raised when a manifest module path cannot be loaded."""


def load_tool_class(module_path: str) -> type[Tool]:
    """Import ``package.module:ClassName`` and verify it is a Tool subclass."""
    if ":" not in module_path:
        raise ToolLoadError(f"invalid module path (expected module:Class): {module_path}")
    module_name, class_name = module_path.rsplit(":", 1)
    if not module_name or not class_name:
        raise ToolLoadError(f"invalid module path: {module_path}")

    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ToolLoadError(f"cannot import module {module_name!r}: {exc}") from exc

    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ToolLoadError(f"class {class_name!r} not found in {module_name!r}") from exc

    if not isinstance(cls, type) or not issubclass(cls, Tool):
        raise ToolLoadError(f"{module_path} is not a Tool subclass")
    return cls


def instantiate_tool(module_path: str) -> Tool:
    cls = load_tool_class(module_path)
    return cls()
