"""Fleet monitoring API (v1.0.0 indigenous observability)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...fleet.service import FleetMonitorService
from ..observability import update_fleet_gauges
from ._deps import get_execution_runtime

router = APIRouter(prefix="/fleet", tags=["fleet"])


def _fleet_service(runtime=Depends(get_execution_runtime)) -> FleetMonitorService:
    return FleetMonitorService(runtime=runtime)


@router.get("/summary")
async def fleet_summary(service: FleetMonitorService = Depends(_fleet_service)) -> dict[str, Any]:
    body = await service.summary()
    update_fleet_gauges(body)
    return body


@router.get("/metrics")
async def fleet_metrics(
    window: str = Query(default="24h", description="Time window e.g. 24h, 12h, 48h"),
    service: FleetMonitorService = Depends(_fleet_service),
) -> dict[str, Any]:
    return await service.metrics(window=window)


@router.get("/workers")
async def fleet_workers(service: FleetMonitorService = Depends(_fleet_service)) -> dict[str, Any]:
    return await service.workers()
