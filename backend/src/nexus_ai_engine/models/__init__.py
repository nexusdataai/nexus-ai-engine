"""Pydantic domain models.

Two layers ship in the library:

- The slim canonical models (:mod:`.job`, :mod:`.journey`, :mod:`.prompt`,
  :mod:`.report`) used by the in-memory engine and the reference FastAPI
  routers' response models.
- The richer MCP/legacy-API models ported from nexus-backend
  (:mod:`.journey_model`, :mod:`.prompt_model`, :mod:`.logs_and_reports_model`)
  consumed by the DynamoDB-backed services and the MCP tools.

Both layers coexist; pick whichever shape your caller expects. Names that
overlap (``JobStatus``, ``JourneyStatus``) keep their canonical lower-case
``str`` Enum values in :mod:`.job` / :mod:`.journey` (used by the in-memory
engine) while the upper-case backend variants live under their original
namespaces in :mod:`.journey_model`.
"""

from __future__ import annotations

from .job import (
    Job,
    JobEvent,
    JobMetrics,
    JobRunRequest,
    JobStatus,
    LogEntry,
    StepResult,
)
from .journey import (
    Journey,
    JourneyCreate,
    JourneyStatus,
    JourneyUpdate,
    Schedule,
    ScheduleCreate,
    ScheduleUpdate,
    Stage,
    StageStatus,
    Step,
)
from .prompt import Prompt, PromptAuditEntry, PromptConfig, PromptUpdate
from .report import AggregateReport, Report, ReportCreate

# ── Backend-ported MCP / legacy-API models ─────────────────────────────────
from .journey_model import (
    JourneyAction,
    JourneyActionRequest,
    JourneyActionResponse,
    JourneyData,
    JourneyListResponse,
    JourneyResponse,
    JourneySummary,
    JobMetrics as JobMetricsLegacy,
    JobStatus as JobStatusLegacy,
    JobStatusUpdate,
    JourneyStatus as JourneyStatusLegacy,
    Priority,
    RuleData,
    RuleScope,
    RuleStatus,
    RuleType,
    StageData,
    StageDefinition,
    StageId,
    convert_to_journey_data,
    convert_to_rule_data,
    convert_to_stage_data,
)
from .logs_and_reports_model import (
    ExportFormat,
    LogLevel,
    LogsAndReportsAction,
    LogsAndReportsActionRequest,
    ReportType,
    create_error_response,
    create_success_response,
)
from .prompt_model import (
    DEFAULT_PROMPTS,
    PromptAuditEntry as PromptAuditEntryLegacy,
    PromptConfig as PromptConfigLegacy,
    PromptEntry,
    PromptListResponse,
    PromptMetadata,
    PromptResetResponse,
    PromptType,
    UpdatePromptRequest,
    UpdatePromptResponse,
    get_default_prompt,
    get_default_prompts,
)

__all__ = [
    "AggregateReport",
    "DEFAULT_PROMPTS",
    "ExportFormat",
    "Job",
    "JobEvent",
    "JobMetrics",
    "JobMetricsLegacy",
    "JobRunRequest",
    "JobStatus",
    "JobStatusLegacy",
    "JobStatusUpdate",
    "Journey",
    "JourneyAction",
    "JourneyActionRequest",
    "JourneyActionResponse",
    "JourneyCreate",
    "JourneyData",
    "JourneyListResponse",
    "JourneyResponse",
    "JourneyStatus",
    "JourneyStatusLegacy",
    "JourneySummary",
    "JourneyUpdate",
    "LogEntry",
    "LogLevel",
    "LogsAndReportsAction",
    "LogsAndReportsActionRequest",
    "Priority",
    "Prompt",
    "PromptAuditEntry",
    "PromptAuditEntryLegacy",
    "PromptConfig",
    "PromptConfigLegacy",
    "PromptEntry",
    "PromptListResponse",
    "PromptMetadata",
    "PromptResetResponse",
    "PromptType",
    "PromptUpdate",
    "Report",
    "ReportCreate",
    "ReportType",
    "RuleData",
    "RuleScope",
    "RuleStatus",
    "RuleType",
    "Schedule",
    "ScheduleCreate",
    "ScheduleUpdate",
    "Stage",
    "StageData",
    "StageDefinition",
    "StageId",
    "StageStatus",
    "Step",
    "StepResult",
    "UpdatePromptRequest",
    "UpdatePromptResponse",
    "convert_to_journey_data",
    "convert_to_rule_data",
    "convert_to_stage_data",
    "create_error_response",
    "create_success_response",
    "get_default_prompt",
    "get_default_prompts",
]
