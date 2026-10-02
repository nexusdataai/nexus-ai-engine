"""Infra monitoring REST API — System SLA summary for Operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

PILLARS = ("performance", "availability", "reliability", "security", "compliance")
APP_TABS = ("executions", "queue", "schedules")


@router.get("/app/{tab}")
async def get_app_trends(
    tab: str,
    window: str = Query("24h", description="Aggregation window: 24h, 7d, or 30d"),
) -> Dict[str, Any]:
    tab = tab.lower()
    if tab not in APP_TABS:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Unknown tab: {tab}", "implemented": list(APP_TABS)},
        )
    if window not in ("24h", "7d", "30d"):
        window = "24h"
    try:
        from ...services.app_trends_service import get_app_trends_service

        return await get_app_trends_service().get_trends(tab, window=window)
    except Exception as exc:
        logger.error("App trends failed: {}", exc)
        return {"tab": tab, "window": window, "kpis": [], "points": [], "error": "Failed to load app trends"}


@router.get("/resources")
async def get_resource_usage(
    window: str = Query("1h", description="Aggregation window: 1h, 24h, or 7d"),
) -> Dict[str, Any]:
    if window not in ("1h", "24h", "7d"):
        window = "1h"
    try:
        from ...services.resource_monitoring_service import get_resource_monitoring_service

        return get_resource_monitoring_service().get_summary(window=window)
    except Exception as exc:
        logger.error("Resource monitoring failed: {}", exc)
        return {
            "window": window,
            "kpis": [],
            "points": [],
            "error": "Failed to load resource usage",
        }


@router.get("/redis")
async def get_redis_overview() -> Dict[str, Any]:
    try:
        from ...services.redis_cache_service import get_redis_cache_service

        return get_redis_cache_service().get_overview()
    except Exception as exc:
        logger.error("Redis overview failed: {}", exc)
        return {"connected": False, "error": "Failed to load Redis overview"}


@router.post("/redis/snapshots/collect")
async def collect_redis_snapshots() -> Dict[str, Any]:
    try:
        from ...services.redis_cache_service import get_redis_cache_service

        return await get_redis_cache_service().collect_snapshots()
    except Exception as exc:
        logger.error("Redis snapshot collect failed: {}", exc)
        return {"collected": False, "error": "Failed to collect snapshots"}


@router.post("/redis/snapshots/flush")
async def flush_redis_snapshots(
    confirm: str = Query(..., description="Must be FLUSH_SNAPSHOTS"),
) -> Dict[str, Any]:
    if confirm != "FLUSH_SNAPSHOTS":
        raise HTTPException(status_code=400, detail="confirm=FLUSH_SNAPSHOTS required")
    try:
        from ...services.redis_cache_service import get_redis_cache_service

        return get_redis_cache_service().flush_snapshots()
    except Exception as exc:
        logger.error("Redis snapshot flush failed: {}", exc)
        return {"flushed": False, "error": "Failed to flush snapshots"}


@router.post("/redis/sse/flush")
async def flush_redis_sse(
    confirm: str = Query(..., description="Must be FLUSH_SSE_HISTORY"),
) -> Dict[str, Any]:
    if confirm != "FLUSH_SSE_HISTORY":
        raise HTTPException(status_code=400, detail="confirm=FLUSH_SSE_HISTORY required")
    try:
        from ...services.redis_cache_service import get_redis_cache_service

        return get_redis_cache_service().flush_sse_history()
    except Exception as exc:
        logger.error("Redis SSE flush failed: {}", exc)
        return {"flushed": False, "error": "Failed to flush SSE history"}


@router.get("/dynamodb")
async def get_dynamodb_overview(
    window: str = Query("1h", description="Aggregation window: 1h, 24h, or 7d"),
) -> Dict[str, Any]:
    if window not in ("1h", "24h", "7d"):
        window = "1h"
    try:
        from ...services.data_store_monitoring_service import get_data_store_monitoring_service

        return get_data_store_monitoring_service().get_dynamodb_overview(window=window)
    except Exception as exc:
        logger.error("DynamoDB overview failed: {}", exc)
        return {"connected": False, "tables": [], "window": window, "error": "Failed to load DynamoDB overview"}


@router.get("/athena")
async def get_athena_overview(
    window: str = Query("1h", description="Aggregation window: 1h, 24h, or 7d"),
) -> Dict[str, Any]:
    if window not in ("1h", "24h", "7d"):
        window = "1h"
    try:
        from ...services.data_store_monitoring_service import get_data_store_monitoring_service

        return get_data_store_monitoring_service().get_athena_overview(window=window)
    except Exception as exc:
        logger.error("Athena overview failed: {}", exc)
        return {"connected": False, "window": window, "error": "Failed to load Athena overview"}


@router.get("/slas")
async def get_sla_summary(
    window: str = Query("1h", description="Aggregation window: 1h or 24h"),
) -> Dict[str, Any]:
    window_hours = 24 if window == "24h" else 1
    try:
        from ...services.sla_monitoring_service import get_sla_monitoring_service

        data = await get_sla_monitoring_service().get_summary(window_hours=window_hours)
        return {
            **data,
            "window": window,
            "source": "sla_monitoring_v2",
        }
    except Exception as exc:
        logger.error("SLA summary failed: {}", exc)
        return {
            "window": window,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_score": None,
            "overall_status": "unknown",
            "pillars": {},
            "error": "Failed to compute SLA summary",
        }


@router.get("/slas/timeline")
async def get_sla_timeline(
    hours: int = Query(24, ge=1, le=168),
) -> Dict[str, Any]:
    try:
        from ...services.sla_monitoring_service import get_sla_monitoring_service

        return await get_sla_monitoring_service().get_timeline(hours=hours)
    except Exception as exc:
        logger.error("SLA timeline failed: {}", exc)
        return {"hours": hours, "points": [], "error": "Failed to load SLA timeline"}


@router.get("/slas/{pillar}")
async def get_sla_pillar_detail(
    pillar: str,
    window: str = Query("1h", description="Aggregation window: 1h or 24h"),
) -> Dict[str, Any]:
    window_hours = 24 if window == "24h" else 1
    pillar = pillar.lower()
    if pillar not in PILLARS:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Unknown pillar: {pillar}", "implemented": list(PILLARS)},
        )
    try:
        from ...services.sla_monitoring_service import get_sla_monitoring_service

        return await get_sla_monitoring_service().get_pillar_detail(pillar, window_hours=window_hours)
    except Exception as exc:
        logger.error("SLA pillar detail failed: {}", exc)
        return {"pillar": pillar, "error": "Failed to compute pillar detail"}
