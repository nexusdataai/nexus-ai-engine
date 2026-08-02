"""Tool base class tests (rc2 tool-base)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from nexus_ai_engine.contracts.tool_request import ToolRequest, ToolRequestMode, ToolResponseStatus
from nexus_ai_engine.tools.base import MockTool, ToolExecutionError
from nexus_tool_sdk import ExecutionContext, ToolRuntime

TENANT_ID = uuid4()
TRACE_ID = "trace-tool-base"


def _req(capability: str, **extra) -> ToolRequest:
    return ToolRequest(
        id=uuid4(),
        version=1,
        created_at=datetime.now(tz=UTC),
        tenant_id=TENANT_ID,
        trace_id=TRACE_ID,
        tool_id="mock",
        tool_version="0.1.0",
        capability=capability,
        mode=ToolRequestMode.READ,
        arguments=extra,
        idempotency_key="k",
        caller_execution_id=uuid4(),
        caller_node_id=uuid4(),
        caller_planner_result_id=uuid4(),
    )


def _runtime() -> ToolRuntime:
    ctx = ExecutionContext(tenant_id=TENANT_ID, trace_id=TRACE_ID)
    return ToolRuntime.create(
        context=ctx,
        vdl_base_url="http://ontology/api/v1/vdl",
        connector_base_url="http://ontology/api/v1/connectors",
        http=httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"rows": []}))),
    )


@pytest.mark.asyncio
async def test_mock_tool_execute_ok():
    tool = MockTool(capabilities=["ping"])
    tool.expect("ping", {"pong": True})
    runtime = _runtime()

    response = await tool.execute(_req("ping"), runtime)
    assert response.status is ToolResponseStatus.OK
    assert response.result == {"pong": True}
    assert tool.calls == [("ping", {})]


@pytest.mark.asyncio
async def test_mock_tool_execute_tool_execution_error():
    tool = MockTool(capabilities=["ping"])
    tool.expect("ping", ToolExecutionError("BAD", "nope", retryable=True))
    runtime = _runtime()

    response = await tool.execute(_req("ping"), runtime)
    assert response.status is ToolResponseStatus.ERROR
    assert response.error is not None
    assert response.error.code == "BAD"
    assert response.error.retryable is True


@pytest.mark.asyncio
async def test_descriptor_has_capabilities():
    tool = MockTool(capabilities=["run"])
    desc = tool.descriptor()
    assert desc.tool_id == "mock"
    assert len(desc.capabilities) == 1
    assert desc.capabilities[0].name == "run"
