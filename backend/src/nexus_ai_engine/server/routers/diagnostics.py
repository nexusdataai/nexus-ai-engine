"""Operations Diagnostics REST API — infrastructure checks for this ai-engine."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from loguru import logger

from ...services.infra_diagnostics_service import CATEGORIES, get_infra_diagnostics_service

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/infrastructure")
async def infra_all() -> Dict[str, Any]:
    try:
        return await get_infra_diagnostics_service().run_all()
    except Exception as exc:
        logger.error("Infrastructure diagnostics failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to run infrastructure diagnostics") from exc


@router.get("/infrastructure/{category}")
async def infra_category(category: str) -> Dict[str, Any]:
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail={"error": f"Unknown category: {category}", "implemented": list(CATEGORIES)})
    try:
        return await get_infra_diagnostics_service().run_category(category)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Infrastructure {} diagnostics failed: {}", category, exc)
        raise HTTPException(status_code=500, detail=f"Failed to run {category} diagnostics") from exc
