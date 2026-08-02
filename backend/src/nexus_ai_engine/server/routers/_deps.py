"""Shared FastAPI dependencies for engine and execution runtime."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status

from ...execution import InMemoryEngine
from ...factory import Engine


def get_engine(request: Request) -> Any:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine is not wired. build_engine() has not been called.",
        )
    return engine


def get_execution_runtime(request: Request):
    engine = get_engine(request)
    if isinstance(engine, InMemoryEngine):
        return engine.execution_runtime
    if isinstance(engine, Engine):
        return engine.execution_runtime
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Execution runtime is not available for this engine type.",
    )


def get_dsl_store(request: Request):
    engine = get_engine(request)
    if isinstance(engine, InMemoryEngine):
        return engine.dsl_store
    if isinstance(engine, Engine):
        return engine.dsl_store
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Journey DSL store is not available.",
    )
