"""Contract tests — nexus-tool-sdk shapes match spec 041 OpenAPI."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from nexus_tool_sdk import (
    ConnectorClient,
    ExecutionContext,
    VdlClient,
    VdlQuerySpec,
)

TENANT = uuid4()
CTX = ExecutionContext(tenant_id=TENANT, trace_id="contract-rc2")


def _openapi_vdl_server(rows: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/query"):
            body = json.loads(request.content)
            assert "virtualEntity" in body
            assert "X-Nexus-Tenant-Id" in request.headers
            return httpx.Response(
                200,
                json={
                    "virtualEntity": body["virtualEntity"],
                    "rows": rows,
                    "metadata": {
                        "sourceTable": "sim.opportunity",
                        "sourceType": "simulator",
                        "durationMs": 10,
                        "rowCount": len(rows),
                        "truncated": False,
                    },
                },
            )
        if path.endswith("/batch-query"):
            body = json.loads(request.content)
            assert "queries" in body
            results = []
            for q in body["queries"]:
                results.append(
                    {
                        "queryId": q.get("queryId"),
                        "virtualEntity": q["virtualEntity"],
                        "rows": rows,
                        "metadata": {"rowCount": len(rows)},
                        "error": None,
                    }
                )
            return httpx.Response(200, json={"results": results, "durationMs": 20})
        return httpx.Response(404)

    return handler


def _openapi_connector_server():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/salesforce/invoke"):
            body = json.loads(request.content)
            assert body["action"] == "soql_query"
            assert "arguments" in body
            assert "context" in body
            return httpx.Response(
                200,
                json={"success": True, "result": {"records": []}, "durationMs": 5},
            )
        return httpx.Response(404)

    return handler


@pytest.mark.asyncio
async def test_contract_vdl_query_shape():
    rows = [{"Opportunity_ID": "OPP-1", "Total_Value": 1000}]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_openapi_vdl_server(rows))
    ) as http:
        client = VdlClient("http://staging/api/v1/vdl", http, CTX)
        result = await client.query("Opportunity", limit=10)
    assert result.virtual_entity == "Opportunity"
    assert result.rows[0]["Opportunity_ID"] == "OPP-1"
    assert result.metadata is not None
    assert result.metadata.source_type == "simulator"


@pytest.mark.asyncio
async def test_contract_vdl_batch_query_shape():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_openapi_vdl_server([]))
    ) as http:
        client = VdlClient("http://staging/api/v1/vdl", http, CTX)
        results = await client.batch_query(
            [
                VdlQuerySpec(query_id="a", virtual_entity="Opportunity", limit=1),
                VdlQuerySpec(query_id="b", virtual_entity="Delivery_Document", limit=5),
            ]
        )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_contract_connector_invoke_shape():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_openapi_connector_server())
    ) as http:
        client = ConnectorClient("http://staging/api/v1/connectors", http, CTX)
        result = await client.invoke("salesforce", "soql_query", {"soql": "SELECT Id FROM Account"})
    assert isinstance(result, dict)
