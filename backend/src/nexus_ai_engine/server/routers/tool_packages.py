"""Tool package publish + catalog API (docs/spec/040, 060)."""

from __future__ import annotations

import json
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from ...contracts.tool_package import ToolPackageManifest
from ...execution import InMemoryEngine
from ...registry.loader import ToolLoadError
from ._deps import get_engine

router = APIRouter()


def _tool_registry(engine):
    registry = getattr(engine, "tool_registry", None)
    if registry is None:
        from ...registry.registry import ToolRegistry
        return ToolRegistry()
    return registry


async def _parse_manifest_body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="empty request body")
    content_type = request.headers.get("content-type", "")
    try:
        if "yaml" in content_type or raw.lstrip().startswith(b"apiVersion"):
            data = yaml.safe_load(raw.decode("utf-8"))
        else:
            data = json.loads(raw)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid manifest body: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="manifest must be a JSON/YAML object")
    return data


def _validate_manifest(data: dict[str, Any]) -> ToolPackageManifest:
    try:
        manifest = ToolPackageManifest.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    if manifest.kind != "ToolPackage":
        raise HTTPException(status_code=422, detail="kind must be ToolPackage")
    return manifest


@router.post("/tool-packages", status_code=status.HTTP_201_CREATED)
async def publish_tool_package(
    request: Request,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    manifest = _validate_manifest(await _parse_manifest_body(request))
    try:
        count = _tool_registry(engine).load_package(manifest)
    except ToolLoadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "package_id": manifest.metadata.id,
        "version": manifest.metadata.version,
        "domain": manifest.metadata.domain,
        "tools_registered": count,
    }


@router.get("/tools")
async def list_tools(
    domain: str | None = None,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    descriptors = _tool_registry(engine).list_tools(domain=domain)
    return {
        "tools": [d.model_dump(mode="json") for d in descriptors],
        "total": len(descriptors),
    }


@router.get("/tools/{tool_id}")
async def get_tool(
    tool_id: str,
    version: str | None = None,
    engine: InMemoryEngine = Depends(get_engine),
) -> dict[str, Any]:
    try:
        tool = _tool_registry(engine).get(tool_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return tool.descriptor().model_dump(mode="json")
