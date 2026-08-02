"""Shared Pydantic contracts (Journey DSL, ExecutionGraph, Tool I/O).

Aligned with nexus-sre contracts per docs/spec/090-nexus-sre-executor-alignment.md.
"""

from nexus_ai_engine.contracts.execution_graph import (
    ExecutionEdge,
    ExecutionGraph,
    ExecutionNode,
    NodeKind,
    NodeVerification,
    RetryPolicy,
)
from nexus_ai_engine.contracts.execution_state import (
    ExecutionState,
    ExecutionStatus,
    NodeState,
    NodeStatus,
    StageRunStatus,
)
from nexus_ai_engine.contracts.journey_dsl import (
    JourneyConcurrency,
    JourneyDefaults,
    JourneyDefinition,
    JourneyMetadata,
    JourneySpec,
    JourneyStage,
    JourneyStep,
    JourneyTrigger,
    RiskClass,
    StepKind,
    StepVerification,
)
from nexus_ai_engine.contracts.tool_descriptor import (
    CapabilityArgumentSpec,
    CapabilityDescriptor,
    PermissionScope,
    ToolAuthor,
    ToolDescriptor,
    ToolSLO,
)
from nexus_ai_engine.contracts.tool_request import (
    ToolCredentialRef,
    ToolError,
    ToolRequest,
    ToolRequestMode,
    ToolResponse,
    ToolResponseStatus,
)

__all__ = [
    "ExecutionEdge",
    "ExecutionGraph",
    "ExecutionNode",
    "ExecutionState",
    "ExecutionStatus",
    "JourneyConcurrency",
    "JourneyDefaults",
    "JourneyDefinition",
    "JourneyMetadata",
    "JourneySpec",
    "JourneyStage",
    "JourneyStep",
    "JourneyTrigger",
    "NodeKind",
    "NodeState",
    "NodeStatus",
    "NodeVerification",
    "RetryPolicy",
    "RiskClass",
    "StageRunStatus",
    "StepKind",
    "StepVerification",
    "CapabilityArgumentSpec",
    "CapabilityDescriptor",
    "PermissionScope",
    "ToolAuthor",
    "ToolDescriptor",
    "ToolSLO",
    "ToolCredentialRef",
    "ToolError",
    "ToolRequest",
    "ToolRequestMode",
    "ToolResponse",
    "ToolResponseStatus",
]
