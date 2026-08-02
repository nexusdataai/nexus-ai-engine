"""Health, readiness, version, and Prometheus metrics endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ... import __version__
from ...config import get_config
from ...execution import InMemoryEngine
from ...stages import list_available_stages
from ..observability import git_sha

router = APIRouter()


def _check_engine(engine: Any | None) -> dict[str, Any]:
    if engine is None:
        return {"status": "unavailable"}
    return {"status": "ok"}


def _check_tool_registry(engine: Any | None) -> dict[str, Any]:
    if engine is None:
        return {"status": "unavailable"}
    stages = list_available_stages()
    if stages:
        return {"status": "ok", "stages": len(stages)}
    if isinstance(engine, InMemoryEngine):
        return {"status": "ok", "mode": "plugin_journey", "stages": 0}
    return {"status": "unavailable", "stages": 0}


def _check_dynamodb(engine: Any | None) -> dict[str, Any]:
    if engine is None or isinstance(engine, InMemoryEngine):
        return {"status": "skipped", "reason": "in_memory_engine"}
    config = get_config()
    if not config.dynamodb_transformation_table:
        return {"status": "unavailable", "reason": "not_configured"}
    return {"status": "ok", "table": config.dynamodb_transformation_table}


def readiness_payload(engine: Any | None) -> tuple[dict[str, Any], bool]:
    checks = {
        "engine": _check_engine(engine),
        "tool_registry": _check_tool_registry(engine),
        "dynamodb": _check_dynamodb(engine),
    }
    ready = all(
        check["status"] in {"ok", "skipped"}
        for check in checks.values()
    )
    body = {
        "ready": ready,
        "version": __version__,
        "checks": checks,
    }
    return body, ready


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readiness")
async def readiness(request: Request) -> JSONResponse:
    engine = getattr(request.app.state, "engine", None)
    body, ready = readiness_payload(engine)
    return JSONResponse(status_code=200 if ready else 503, content=body)


@router.get("/version")
async def version() -> dict[str, str]:
    config = get_config()
    return {
        "name": "nexus-ai-engine",
        "service": "nexus-ai-engine",
        "version": __version__,
        "env": config.environment,
        "git_sha": git_sha(),
    }


@router.get("/metrics")
async def metrics(request: Request) -> PlainTextResponse:
    registry = request.app.state.metrics_registry
    return PlainTextResponse(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
