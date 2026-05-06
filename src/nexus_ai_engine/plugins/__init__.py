"""Plugin specification models, YAML tool executor, and runtime hooks.

The plugin discovery / persistence layer (``PluginService``) stays in the
host application (nexus-backend); only the schema + executor the journey
runtime needs ship in the library.
"""

from .plugin_models import (
    JourneyDefinition,
    JourneyStep,
    JourneyStepGlue,
    JourneyStepOutput,
    PluginConfig,
    PluginManifest,
    PluginPermissions,
    PluginRecord,
    PluginStatus,
    ToolCompareStep,
    ToolDefinition,
    ToolImplementation,
    ToolImplementationStep,
    ToolQueryStep,
)
from .runtime import (
    PluginRuntime,
    build_virtual_query_request,
    get_runtime,
    set_runtime,
)
from .yaml_tool_executor import YAMLToolExecutor, _resolve_var, _resolve_params

__all__ = [
    "JourneyDefinition",
    "JourneyStep",
    "JourneyStepGlue",
    "JourneyStepOutput",
    "PluginConfig",
    "PluginManifest",
    "PluginPermissions",
    "PluginRecord",
    "PluginRuntime",
    "PluginStatus",
    "ToolCompareStep",
    "ToolDefinition",
    "ToolImplementation",
    "ToolImplementationStep",
    "ToolQueryStep",
    "YAMLToolExecutor",
    "_resolve_params",
    "_resolve_var",
    "build_virtual_query_request",
    "get_runtime",
    "set_runtime",
]
