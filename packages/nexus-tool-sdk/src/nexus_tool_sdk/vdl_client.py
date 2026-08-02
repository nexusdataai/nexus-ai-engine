"""VDL HTTP client — POST /api/v1/vdl/query and batch-query."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from nexus_tool_sdk.context import ExecutionContext
from nexus_tool_sdk.errors import VdlError


class VirtualFilter(BaseModel):
    field: str
    operator: str
    value: Any | None = None


class VdlQueryMetadata(BaseModel):
    source_table: str | None = Field(default=None, alias="sourceTable")
    source_type: str | None = Field(default=None, alias="sourceType")
    mapping_rule_id: str | None = Field(default=None, alias="mappingRuleId")
    duration_ms: int | None = Field(default=None, alias="durationMs")
    row_count: int | None = Field(default=None, alias="rowCount")
    truncated: bool | None = None

    model_config = {"populate_by_name": True}


class VdlQueryResult(BaseModel):
    virtual_entity: str = Field(alias="virtualEntity")
    rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata: VdlQueryMetadata | None = None
    query_id: str | None = Field(default=None, alias="queryId")
    error: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class VdlQuerySpec(BaseModel):
    query_id: str | None = Field(default=None, alias="queryId")
    virtual_entity: str = Field(alias="virtualEntity")
    fields: list[str] | None = None
    filters: list[VirtualFilter | dict[str, Any]] | None = None
    limit: int = 50
    offset: int = 0

    model_config = {"populate_by_name": True}


_RETRYABLE_STATUS = frozenset({429, 503})


def _vdl_error_from_response(resp: httpx.Response) -> VdlError:
    body: dict[str, Any] = {}
    try:
        body = resp.json()
    except Exception:
        pass
    code = str(body.get("code") or body.get("error") or f"http_{resp.status_code}")
    message = str(body.get("message") or body.get("detail") or resp.reason_phrase or "VDL request failed")
    retryable = resp.status_code in _RETRYABLE_STATUS or bool(body.get("retryable"))
    return VdlError(code, message, retryable=retryable, status_code=resp.status_code, details=body)


class VdlClient:
    """Client for ontology Virtual Data Layer API."""

    def __init__(
        self,
        base_url: str,
        http: httpx.AsyncClient,
        context: ExecutionContext,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http
        self._context = context

    def _headers(self) -> dict[str, str]:
        return self._context.forward_headers()

    async def query(
        self,
        entity: str,
        *,
        filters: list[dict[str, Any] | VirtualFilter] | None = None,
        fields: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> VdlQueryResult:
        payload: dict[str, Any] = {
            "virtualEntity": entity,
            "limit": limit,
            "offset": offset,
        }
        if fields is not None:
            payload["fields"] = fields
        if filters is not None:
            payload["filters"] = [
                f.model_dump(by_alias=True, exclude_none=True) if isinstance(f, VirtualFilter) else f
                for f in filters
            ]

        resp = await self._http.post(f"{self._base_url}/query", json=payload, headers=self._headers())
        if resp.status_code >= 400:
            raise _vdl_error_from_response(resp)
        data = resp.json()
        return VdlQueryResult.model_validate(data)

    async def query_one(self, entity: str, **kwargs: Any) -> dict[str, Any] | None:
        result = await self.query(entity, limit=1, **kwargs)
        return result.rows[0] if result.rows else None

    async def batch_query(self, requests: list[VdlQuerySpec]) -> list[VdlQueryResult]:
        if not requests:
            return []
        queries = []
        for spec in requests:
            item: dict[str, Any] = {
                "virtualEntity": spec.virtual_entity,
                "limit": spec.limit,
                "offset": spec.offset,
            }
            if spec.query_id is not None:
                item["queryId"] = spec.query_id
            if spec.fields is not None:
                item["fields"] = spec.fields
            if spec.filters is not None:
                item["filters"] = [
                    f.model_dump(by_alias=True, exclude_none=True) if isinstance(f, VirtualFilter) else f
                    for f in spec.filters
                ]
            queries.append(item)

        resp = await self._http.post(
            f"{self._base_url}/batch-query",
            json={"queries": queries, "parallel": True},
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            raise _vdl_error_from_response(resp)

        body = resp.json()
        results: list[VdlQueryResult] = []
        for item in body.get("results", []):
            if item.get("error"):
                err = item["error"]
                raise VdlError(
                    str(err.get("code", "batch_query_failed")),
                    str(err.get("message", "batch query partial failure")),
                    retryable=bool(err.get("retryable")),
                    details=err,
                )
            results.append(VdlQueryResult.model_validate(item))
        return results
