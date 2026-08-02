"""nexus-tool-sdk unit tests (httpx mock transport)."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from nexus_tool_sdk import (
    ConnectorClient,
    ConnectorError,
    ExecutionContext,
    ToolRuntime,
    VdlClient,
    VdlError,
    VdlQuerySpec,
)

TENANT = uuid4()
EXEC_ID = uuid4()
CTX = ExecutionContext(
    tenant_id=TENANT,
    trace_id="trace-rc2",
    execution_id=EXEC_ID,
    tool_id="o2c_match",
    step_id="match-step",
    idempotency_key="exec:node:1",
)


def _vdl_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_vdl_query_returns_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/query")
        assert request.headers["X-Nexus-Tenant-Id"] == str(TENANT)
        body = json.loads(request.content)
        assert body["virtualEntity"] == "Opportunity"
        return httpx.Response(
            200,
            json={
                "virtualEntity": "Opportunity",
                "rows": [{"Opportunity_ID": "OPP-1"}],
                "metadata": {"rowCount": 1, "durationMs": 12},
            },
        )

    async with httpx.AsyncClient(transport=_vdl_transport(handler)) as http:
        client = VdlClient("http://ontology/api/v1/vdl", http, CTX)
        result = await client.query(
            "Opportunity",
            filters=[{"field": "Opportunity_ID", "operator": "eq", "value": "OPP-1"}],
        )
    assert result.rows[0]["Opportunity_ID"] == "OPP-1"
    assert result.metadata is not None
    assert result.metadata.row_count == 1


@pytest.mark.asyncio
async def test_vdl_query_one_returns_none_when_empty():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"virtualEntity": "Opportunity", "rows": []})

    async with httpx.AsyncClient(transport=_vdl_transport(handler)) as http:
        client = VdlClient("http://ontology/api/v1/vdl", http, CTX)
        row = await client.query_one("Opportunity")
    assert row is None


@pytest.mark.asyncio
async def test_vdl_query_raises_on_http_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": "entity_not_found", "message": "unknown entity"})

    async with httpx.AsyncClient(transport=_vdl_transport(handler)) as http:
        client = VdlClient("http://ontology/api/v1/vdl", http, CTX)
        with pytest.raises(VdlError) as exc:
            await client.query("Missing_Entity")
    assert exc.value.code == "entity_not_found"
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_vdl_batch_query():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/batch-query")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "queryId": "opp",
                        "virtualEntity": "Opportunity",
                        "rows": [{"Opportunity_ID": "OPP-1"}],
                        "metadata": {"rowCount": 1},
                        "error": None,
                    }
                ],
                "durationMs": 50,
            },
        )

    async with httpx.AsyncClient(transport=_vdl_transport(handler)) as http:
        client = VdlClient("http://ontology/api/v1/vdl", http, CTX)
        results = await client.batch_query(
            [VdlQuerySpec(query_id="opp", virtual_entity="Opportunity", limit=1)]
        )
    assert len(results) == 1
    assert results[0].rows[0]["Opportunity_ID"] == "OPP-1"


@pytest.mark.asyncio
async def test_connector_invoke_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/salesforce/invoke")
        body = json.loads(request.content)
        assert body["action"] == "create_lead"
        assert body["idempotencyKey"] == "exec:node:1"
        return httpx.Response(
            200,
            json={"success": True, "result": {"leadId": "00Q123"}, "durationMs": 100},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ConnectorClient("http://ontology/api/v1/connectors", http, CTX)
        result = await client.invoke("salesforce", "create_lead", {"email": "a@b.com"})
    assert result["leadId"] == "00Q123"


@pytest.mark.asyncio
async def test_connector_invoke_failure_in_body():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": False,
                "error": {"code": "connector_error", "message": "rate limited", "retryable": True},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ConnectorClient("http://ontology/api/v1/connectors", http, CTX)
        with pytest.raises(ConnectorError) as exc:
            await client.invoke("salesforce", "create_lead", {})
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_tool_runtime_factory():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/vdl/query" in str(request.url):
            return httpx.Response(200, json={"virtualEntity": "X", "rows": []})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        runtime = ToolRuntime.create(
            context=CTX,
            vdl_base_url="http://ontology/api/v1/vdl",
            connector_base_url="http://ontology/api/v1/connectors",
            http=http,
        )
        result = await runtime.vdl.query("X")
    assert result.virtual_entity == "X"
    assert runtime.ontology_base_url == "http://ontology/api/v1"
