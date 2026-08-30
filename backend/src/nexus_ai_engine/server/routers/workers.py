"""Worker registry and scaling API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.job_queue_service import is_queue_mode, redis_available
from ...services.worker_management_service import get_worker_management_service

router = APIRouter(prefix="/workers", tags=["workers"])


class ScaleWorkersRequest(BaseModel):
    replicas: int = Field(ge=0, le=50)


class AutoscalingRequest(BaseModel):
    enabled: bool
    min_replicas: int = Field(default=1, ge=0, le=50)
    max_replicas: int = Field(default=10, ge=1, le=50)
    lag_threshold: int = Field(default=5, ge=1, le=1000)


def _service():
    return get_worker_management_service()


@router.get("/summary")
async def workers_summary() -> dict[str, Any]:
    return _service().get_summary()


@router.get("")
async def list_workers() -> dict[str, Any]:
    if not is_queue_mode():
        return {
            "workers": [],
            "generated_at": _service().get_summary()["generated_at"],
            "message": "Worker registry requires JOB_EXECUTION_MODE=queue",
        }
    return _service().list_workers()


@router.patch("/scale")
async def scale_workers(body: ScaleWorkersRequest) -> dict[str, Any]:
    if not is_queue_mode():
        raise HTTPException(status_code=503, detail="Scaling requires JOB_EXECUTION_MODE=queue")
    svc = _service()
    if not svc.k8s_available:
        raise HTTPException(status_code=503, detail="Kubernetes API unavailable; cannot scale workers")
    try:
        return svc.scale_workers(body.replicas)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/autoscaling")
async def configure_autoscaling(body: AutoscalingRequest) -> dict[str, Any]:
    if not is_queue_mode():
        raise HTTPException(status_code=503, detail="Autoscaling requires JOB_EXECUTION_MODE=queue")
    svc = _service()
    if not svc.k8s_available:
        raise HTTPException(status_code=503, detail="Kubernetes API unavailable; cannot configure autoscaling")
    try:
        return svc.configure_autoscaling(
            enabled=body.enabled,
            min_replicas=body.min_replicas,
            max_replicas=body.max_replicas,
            lag_threshold=body.lag_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
