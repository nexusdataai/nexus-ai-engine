"""Journey DSL API routes (spec 060) — mounted before legacy journey handlers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...contracts.journey_dsl import JourneyDefinition
from ...execution import InMemoryEngine
from ...journeys import DslJourneyStore, JourneyCompiler, JourneyValidator, ValidationResult
from ...journeys.service import JourneyVersionConflictError
from ._deps import get_engine

router = APIRouter()


class ValidateRequest(BaseModel):
    journey: dict[str, Any] | None = None
    strict_tools: bool = False


class ImportRequest(BaseModel):
    yaml_content: str | None = None
    journey: dict[str, Any] | None = None


class CloneRequest(BaseModel):
    new_id: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")


def _dsl_store(engine: InMemoryEngine) -> DslJourneyStore:
    return engine.dsl_store


async def _parse_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="empty request body")
    if "yaml" in content_type or raw.lstrip().startswith(b"apiVersion"):
        try:
            text = raw.decode("utf-8")
            if text.lstrip().startswith("{"):
                import json

                data = json.loads(text)
            else:
                data = yaml.safe_load(text)
        except (yaml.YAMLError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid YAML: {exc}") from exc
    else:
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON/YAML object")
    return data


def _validator_for_engine(engine: InMemoryEngine) -> JourneyValidator:
    return JourneyValidator(known_tools=engine.known_tool_ids())


@router.post("/validate", response_model=ValidationResult)
async def validate_journey_dsl(
    request: Request,
    strict_tools: bool = False,
    engine: InMemoryEngine = Depends(get_engine),
) -> ValidationResult:
    data = await _parse_body(request)
    return _validator_for_engine(engine).validate(data, strict_tools=strict_tools)


@router.post("/import", response_model=JourneyDefinition, status_code=status.HTTP_201_CREATED)
async def import_journey(
    request: Request,
    engine: InMemoryEngine = Depends(get_engine),
) -> JourneyDefinition:
    data = await _parse_body(request)
    result = _validator_for_engine(engine).validate(data)
    if not result.valid:
        raise HTTPException(status_code=422, detail=result.model_dump())
    definition = JourneyDefinition.model_validate(data)
    try:
        return _dsl_store(engine).create(definition)
    except JourneyVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/dsl", response_model=list[dict[str, Any]])
async def list_dsl_journeys(engine: InMemoryEngine = Depends(get_engine)) -> list[dict[str, Any]]:
    store = _dsl_store(engine)
    items = []
    for definition in store.list_all():
        items.append(
            {
                "id": definition.metadata.id,
                "version": definition.metadata.version,
                "display_name": definition.spec.display_name,
                "labels": definition.metadata.labels,
            }
        )
    return items


@router.get("/{journey_id}/versions", response_model=list[int])
async def list_versions(journey_id: str, engine: InMemoryEngine = Depends(get_engine)) -> list[int]:
    versions = _dsl_store(engine).list_versions(journey_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    return versions


@router.get("/{journey_id}/versions/{version}", response_model=JourneyDefinition)
async def get_version(
    journey_id: str, version: int, engine: InMemoryEngine = Depends(get_engine)
) -> JourneyDefinition:
    definition = _dsl_store(engine).get(journey_id, version)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} v{version} not found")
    return definition


@router.get("/{journey_id}/export")
async def export_journey(
    journey_id: str,
    version: int | None = None,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, str]:
    try:
        content = _dsl_store(engine).export_yaml(journey_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found") from exc
    return {"journey_id": journey_id, "yaml": content}


@router.post("/{journey_id}/validate", response_model=ValidationResult)
async def validate_stored_journey(
    journey_id: str,
    request: Request,
    engine: InMemoryEngine = Depends(get_engine),
    strict_tools: bool = False,
) -> ValidationResult:
    body = await request.body()
    if body:
        data = await _parse_body(request)
    else:
        data = _dsl_store(engine).get(journey_id)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
        data = data.model_dump(by_alias=True)
    return _validator_for_engine(engine).validate(data, strict_tools=strict_tools)


@router.post("/{journey_id}/clone", response_model=JourneyDefinition, status_code=status.HTTP_201_CREATED)
async def clone_dsl_journey(
    journey_id: str,
    body: CloneRequest,
    engine: InMemoryEngine = Depends(get_engine),
) -> JourneyDefinition:
    try:
        return _dsl_store(engine).clone(journey_id, new_id=body.new_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found") from exc


@router.post("/{journey_id}/compile")
async def compile_journey(
    journey_id: str,
    version: int | None = None,
    strict_tool_validation: bool = False,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    definition = _dsl_store(engine).get(journey_id, version)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")
    if strict_tool_validation:
        result = _validator_for_engine(engine).validate(
            definition.model_dump(by_alias=True),
            strict_tools=True,
        )
        if not result.valid:
            raise HTTPException(status_code=422, detail=result.model_dump())
    graph = JourneyCompiler().compile(definition, tenant_id=uuid4(), trace_id=f"compile:{journey_id}")
    return graph.model_dump(mode="json")


@router.post("/dsl", response_model=JourneyDefinition, status_code=status.HTTP_201_CREATED)
async def create_dsl_journey(
    request: Request,
    engine: InMemoryEngine = Depends(get_engine),
) -> JourneyDefinition:
    data = await _parse_body(request)
    result = _validator_for_engine(engine).validate(data)
    if not result.valid:
        raise HTTPException(status_code=422, detail=result.model_dump())
    definition = JourneyDefinition.model_validate(data)
    try:
        return _dsl_store(engine).create(definition)
    except JourneyVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
