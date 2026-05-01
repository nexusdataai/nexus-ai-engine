"""Shared FastAPI dependency for grabbing the InMemoryEngine off app.state."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from ...execution import InMemoryEngine


def get_engine(request: Request) -> InMemoryEngine:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine is not wired. build_engine() has not been called.",
        )
    return engine
