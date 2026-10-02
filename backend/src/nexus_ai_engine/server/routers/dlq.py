"""Operations Dead Letter Queue REST API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from ...services.dlq_service import get_dlq_service

router = APIRouter(prefix="/dlq", tags=["dlq"])


class DlqKeyRequest(BaseModel):
    sk: str


class DlqBulkRequest(BaseModel):
    sks: List[str]


@router.get("")
async def list_dlq(
    status: Optional[str] = Query(None, description="pending_review | reprocessed | dismissed"),
    limit: int = Query(100, ge=1, le=200),
) -> Dict[str, Any]:
    try:
        return get_dlq_service().list_entries(status=status, limit=limit)
    except Exception as exc:
        logger.error("DLQ list failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to list DLQ entries") from exc


@router.post("/import-failed")
async def import_failed_jobs(limit: int = Query(100, ge=1, le=200)) -> Dict[str, Any]:
    try:
        return get_dlq_service().import_failed_jobs(limit=limit)
    except Exception as exc:
        logger.error("DLQ import failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to import failed jobs") from exc


@router.post("/reprocess")
async def reprocess_dlq(body: DlqKeyRequest) -> Dict[str, Any]:
    try:
        return await get_dlq_service().reprocess(body.sk)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("DLQ reprocess failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to reprocess DLQ entry") from exc


@router.post("/reprocess-bulk")
async def reprocess_dlq_bulk(body: DlqBulkRequest) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for sk in body.sks:
        try:
            results.append(await get_dlq_service().reprocess(sk))
        except Exception as exc:
            results.append({"reprocessed": False, "sk": sk, "error": str(exc)})
    return {
        "requested": len(body.sks),
        "reprocessed": sum(1 for r in results if r.get("reprocessed")),
        "results": results,
    }


@router.post("/dismiss")
async def dismiss_dlq(body: DlqKeyRequest) -> Dict[str, Any]:
    try:
        return get_dlq_service().dismiss(body.sk)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("DLQ dismiss failed: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to dismiss DLQ entry") from exc
