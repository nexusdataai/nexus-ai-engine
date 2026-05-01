"""Journey, Stage, Step, Schedule domain models.

Shapes modeled on nexus-backend/src/models/journey_model.py and the JSON
returned by /api/v1/journeys in nexus-ui's transformationJourneyService.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JourneyStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    paused = "paused"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Step(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    order: int = 0


class Stage(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    order: int = 0
    status: StageStatus = StageStatus.pending
    steps: list[Step] = Field(default_factory=list)


class Journey(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    capability: Optional[str] = None
    kind: Optional[str] = None
    status: JourneyStatus = JourneyStatus.created
    created_at: datetime
    updated_at: datetime
    stages: list[Stage] = Field(default_factory=list)
    jobs_total: int = 0
    jobs_done: int = 0
    jobs_running: int = 0
    jobs_failed: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    extras: dict[str, Any] = Field(default_factory=dict)


class JourneyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    capability: Optional[str] = None
    kind: Optional[str] = None
    stages: list[Stage] = Field(default_factory=list)


class JourneyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capability: Optional[str] = None


class Schedule(BaseModel):
    id: str
    journey_id: str
    stage_id: str
    interval_minutes: int
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScheduleCreate(BaseModel):
    journey_id: str
    stage_id: str
    interval_minutes: int = 15
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    interval_minutes: Optional[int] = None
    enabled: Optional[bool] = None
