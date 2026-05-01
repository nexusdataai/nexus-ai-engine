"""Report models — per-step and aggregated."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Report(BaseModel):
    id: str
    journey_id: str
    job_id: str
    step_id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReportCreate(BaseModel):
    step_id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


class AggregateReport(BaseModel):
    journey_id: str
    generated_at: datetime
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    total_calls_processed: int = 0
    total_errors: int = 0
    top_error_messages: list[str] = Field(default_factory=list)
    per_stage: dict[str, Any] = Field(default_factory=dict)
