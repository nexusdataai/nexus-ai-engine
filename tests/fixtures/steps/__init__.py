"""Deterministic step tools for the nexus-ai-engine test suite.

These tools implement the `StepTool` protocol defined in
`nexus_ai_engine.execution.in_memory_engine` and are registered on an
InMemoryEngine via `engine.register_step_tool(name, tool)`. They are
used by:

- Plugin-journey YAML samples under `tests/journeys/samples/` that
  declare `type: tool` / `tool: <name>` on their steps.
- Direct-wire tests that build an engine, register tools, and execute
  jobs without needing the YAML runner.

The shipped random-simulation execution path is untouched: journeys
whose steps do NOT declare `type: tool` continue to use the lively
random simulator, so the UI demo's behavior is unchanged.

Each tool is fully deterministic given its `step_def.input` payload.
Tools that appear random (flaky) derive their PRNG state from a
seed passed in `input`, so assertions remain stable across runs.
"""

from __future__ import annotations

from .core import (
    ALL_TOOLS,
    register_all,
    tool_cancel_checkpoint,
    tool_count_to,
    tool_cpu_spin,
    tool_emit_report,
    tool_fail_after,
    tool_flaky,
    tool_gather,
    tool_noop,
    tool_sleep,
    tool_transform,
)

__all__ = [
    "ALL_TOOLS",
    "register_all",
    "tool_cancel_checkpoint",
    "tool_count_to",
    "tool_cpu_spin",
    "tool_emit_report",
    "tool_fail_after",
    "tool_flaky",
    "tool_gather",
    "tool_noop",
    "tool_sleep",
    "tool_transform",
]
