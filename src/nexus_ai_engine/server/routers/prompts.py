"""Prompts router — activated against the in-memory engine.

PORT FIDELITY CHECKLIST — do not simplify when porting the DynamoDB adapter.
Source: /opt/mycode/nexus/nexus-backend/src/apis/prompts_api.py

    GET    ""              (list)     lines 49-75    (list_prompts)
    GET    /types                      lines 76-93    (prompt_types)
    GET    /{prompt_id}                lines 94-128   (get_prompt)
    PUT    /{prompt_id}                lines 129-173  (update_prompt)
    POST   /reset                      lines 174-203  (reset_prompts)
    GET    /audit/log                  lines 204-end  (audit_log)

Current status: activated against an in-memory engine. When the DynamoDB
adapter lands in phase 10 it replaces the backing store; handler bodies
stay identical.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...execution import InMemoryEngine
from ...models import Prompt, PromptAuditEntry, PromptUpdate
from ._deps import get_engine

router = APIRouter()


@router.get("", response_model=list[Prompt])
async def list_prompts(engine: InMemoryEngine = Depends(get_engine)) -> list[Prompt]:
    return await engine.list_prompts()


@router.get("/types")
async def prompt_types(engine: InMemoryEngine = Depends(get_engine)) -> dict:
    return {"types": await engine.list_prompt_types()}


@router.get("/{prompt_id}", response_model=Prompt)
async def get_prompt(prompt_id: str, engine: InMemoryEngine = Depends(get_engine)) -> Prompt:
    p = await engine.get_prompt(prompt_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")
    return p


@router.put("/{prompt_id}", response_model=Prompt)
async def update_prompt(
    prompt_id: str, body: PromptUpdate, engine: InMemoryEngine = Depends(get_engine)
) -> Prompt:
    p = await engine.update_prompt(prompt_id, body)
    if not p:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")
    return p


@router.post("/reset", response_model=list[Prompt])
async def reset_prompts(engine: InMemoryEngine = Depends(get_engine)) -> list[Prompt]:
    return await engine.reset_prompts()


@router.get("/audit/log", response_model=list[PromptAuditEntry])
async def audit_log(
    limit: int = 100, engine: InMemoryEngine = Depends(get_engine)
) -> list[PromptAuditEntry]:
    return await engine.prompt_audit_log(limit=limit)
