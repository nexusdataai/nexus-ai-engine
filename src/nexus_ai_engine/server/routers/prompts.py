"""Prompts router (list, types, get, update, reset, audit).

PORT FIDELITY CHECKLIST — do not simplify when porting.
Source: /opt/mycode/nexus/nexus-backend/src/apis/prompts_api.py

    GET    ""              (list)     lines 49-75    (list_prompts)
    GET    /types                      lines 76-93    (prompt_types)
    GET    /{prompt_id}                lines 94-128   (get_prompt)
    PUT    /{prompt_id}                lines 129-173  (update_prompt)
    POST   /reset                      lines 174-203  (reset_prompts)
    GET    /audit/log                  lines 204-end  (audit_log)

Routes activate in phase 5 of the extraction plan; until then they return 501.

See docs/ROUTE_PARITY.md for the full rules.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(route: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{route} is not yet activated in nexus-ai-engine. Ports land in phase 5.",
    )


@router.get("")
async def list_prompts() -> dict:
    raise _not_implemented("GET /")


@router.get("/types")
async def prompt_types() -> dict:
    raise _not_implemented("GET /types")


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str) -> dict:
    raise _not_implemented("GET /{prompt_id}")


@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, payload: dict[str, Any]) -> dict:
    raise _not_implemented("PUT /{prompt_id}")


@router.post("/reset")
async def reset_prompts() -> dict:
    raise _not_implemented("POST /reset")


@router.get("/audit/log")
async def audit_log() -> dict:
    raise _not_implemented("GET /audit/log")
