"""Prompt catalog models — minimal subset of nexus-backend prompt_model.py."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Prompt(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    type: str = "system"  # system | user | assistant
    content: str
    version: int = 1
    updated_at: datetime
    is_default: bool = False


class PromptUpdate(BaseModel):
    content: str
    note: Optional[str] = None


class PromptAuditEntry(BaseModel):
    timestamp: datetime
    prompt_id: str
    action: str  # updated | reset | created
    actor: str = "ui"
    note: Optional[str] = None
    previous_content: Optional[str] = None


class PromptConfig(BaseModel):
    prompts: list[Prompt] = Field(default_factory=list)
    audit: list[PromptAuditEntry] = Field(default_factory=list)
