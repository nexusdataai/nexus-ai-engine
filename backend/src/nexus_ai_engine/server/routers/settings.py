"""Runtime settings for workers, queue, and scheduler."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class AutoscalingBody(BaseModel):
    enabled: bool
    min_replicas: int = Field(default=1, ge=0, le=50)
    max_replicas: int = Field(default=10, ge=1, le=50)
    lag_threshold: int = Field(default=5, ge=1, le=1000)


class UpdateSettingsRequest(BaseModel):
    replicas: Optional[int] = Field(None, ge=0, le=50)
    worker_threads: Optional[int] = Field(None, ge=1, le=16)
    max_global_jobs: Optional[int] = Field(None, ge=1, le=50)
    scheduler_interval_sec: Optional[int] = Field(None, ge=5, le=3600)
    autoscaling: Optional[AutoscalingBody] = None


@router.get("")
async def read_settings() -> dict[str, Any]:
    return get_settings()


@router.patch("")
async def patch_settings(body: UpdateSettingsRequest) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No settings to update")
    try:
        return update_settings(
            replicas=payload.get("replicas"),
            worker_threads=payload.get("worker_threads"),
            max_global_jobs=payload.get("max_global_jobs"),
            scheduler_interval_sec=payload.get("scheduler_interval_sec"),
            autoscaling=payload.get("autoscaling"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
