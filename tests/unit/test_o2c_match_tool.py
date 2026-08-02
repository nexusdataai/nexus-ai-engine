"""Unit tests for O2C match tool (VDL mocked via httpx transport)."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from nexus_tool_sdk import ExecutionContext, ToolRuntime
from o2c_tools.match import O2cMatchOrderDeliveryInvoiceTool

from nexus_ai_engine.contracts.tool_request import ToolRequest, ToolRequestMode


TENANT = uuid4()
EXEC_ID = uuid4()
CTX = ExecutionContext(tenant_id=TENANT, trace_id="trace-o2c", execution_id=EXEC_ID)


def _vdl_handler(rows_by_entity: dict[str, list[dict]]):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        entity = body["virtualEntity"]
        rows = rows_by_entity.get(entity, [])
        filters = body.get("filters") or []
        if filters:
            field = filters[0]["field"]
            value = filters[0]["value"]
            rows = [r for r in rows if str(r.get(field)) == str(value)]
        limit = body.get("limit", 50)
        return httpx.Response(
            200,
            json={"virtualEntity": entity, "rows": rows[:limit], "metadata": {"rowCount": len(rows)}},
        )

    return handler


def _make_request(**arguments) -> ToolRequest:
    from datetime import datetime, timezone

    return ToolRequest(
        id=uuid4(),
        version=1,
        created_at=datetime.now(timezone.utc),
        tenant_id=TENANT,
        trace_id="trace-o2c",
        tool_id="o2c_match_order_delivery_invoice",
        tool_version="1.0.0",
        capability="match_order_delivery_invoice",
        mode=ToolRequestMode.READ,
        idempotency_key="exec:node:1",
        caller_execution_id=EXEC_ID,
        caller_node_id=uuid4(),
        caller_planner_result_id=uuid4(),
        arguments=arguments,
    )


@pytest.mark.asyncio
async def test_o2c_match_matched():
    rows = {
        "Opportunity": [{"Opportunity_ID": "OPP-1", "Total_Value": 1000}],
        "Opportunity_Line_Item": [{"Opportunity_ID": "OPP-1", "Quantity": 10, "Total_Price": 1000}],
        "Delivery_Document": [{"Sales_Order_ID": "OPP-1", "Delivery_ID": "DEL-1", "Qty": 10}],
        "AR_Invoice": [{"Linked_Delivery_ID": "DEL-1", "Invoice_ID": "INV-1", "Total_Amount": 1000}],
    }
    tool = O2cMatchOrderDeliveryInvoiceTool()
    async with httpx.AsyncClient(transport=httpx.MockTransport(_vdl_handler(rows))) as http:
        runtime = ToolRuntime.create(
            context=CTX,
            vdl_base_url="http://ontology/api/v1/vdl",
            connector_base_url="http://ontology/api/v1/connectors",
            http=http,
        )
        resp = await tool.execute(_make_request(opportunity_id="OPP-1"), runtime)
    assert resp.status.value == "ok"
    assert resp.result["match_status"] == "matched"
    assert resp.result["discrepancies"] == []


@pytest.mark.asyncio
async def test_o2c_match_missing_delivery():
    rows = {
        "Opportunity": [{"Opportunity_ID": "OPP-2", "Total_Value": 500}],
        "Opportunity_Line_Item": [{"Opportunity_ID": "OPP-2", "Quantity": 5, "Total_Price": 500}],
        "Delivery_Document": [],
    }
    tool = O2cMatchOrderDeliveryInvoiceTool()
    async with httpx.AsyncClient(transport=httpx.MockTransport(_vdl_handler(rows))) as http:
        runtime = ToolRuntime.create(
            context=CTX,
            vdl_base_url="http://ontology/api/v1/vdl",
            connector_base_url="http://ontology/api/v1/connectors",
            http=http,
        )
        resp = await tool.execute(_make_request(opportunity_id="OPP-2"), runtime)
    assert resp.result["match_status"] == "missing_delivery"


@pytest.mark.asyncio
async def test_o2c_match_order_not_found():
    tool = O2cMatchOrderDeliveryInvoiceTool()
    async with httpx.AsyncClient(transport=httpx.MockTransport(_vdl_handler({}))) as http:
        runtime = ToolRuntime.create(
            context=CTX,
            vdl_base_url="http://ontology/api/v1/vdl",
            connector_base_url="http://ontology/api/v1/connectors",
            http=http,
        )
        resp = await tool.execute(_make_request(opportunity_id="OPP-MISSING"), runtime)
    assert resp.result["match_status"] == "order_not_found"
