"""Job and JobEvent domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepResult(BaseModel):
    step_id: str
    status: JobStatus = JobStatus.queued
    progress: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error: Optional[str] = None
    log_count: int = 0


class JobMetrics(BaseModel):
    calls_processed: int = 0
    errors: int = 0
    warnings: int = 0
    success_rate: float = 100.0
    extras: dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    id: str
    journey_id: str
    stage_id: str
    stage_name: str
    execution_number: int
    status: JobStatus = JobStatus.queued
    progress: int = 0
    triggered_by: str = "ui"
    trigger_reason: str = "manual"
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    current_step_id: Optional[str] = None
    step_results: list[StepResult] = Field(default_factory=list)
    metrics: JobMetrics = Field(default_factory=JobMetrics)
    error_message: Optional[str] = None


class JobRunRequest(BaseModel):
    stage_id: str
    triggered_by: str = "ui"
    reason: Optional[str] = None


class LogEntry(BaseModel):
    timestamp: datetime
    level: str = "INFO"
    message: str
    step_id: Optional[str] = None


class JobEvent(BaseModel):
    """Event emitted over SSE during simulated job execution."""

    type: str  # step_status | log | task_progress | job_complete | error
    job_id: str
    step_id: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
