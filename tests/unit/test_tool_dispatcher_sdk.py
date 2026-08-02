"""ToolDispatcher registry + ToolRuntime integration tests."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from nexus_ai_engine.contracts.tool_package import (
    OntologyApiSpec,
    ToolPackageEntry,
    ToolPackageManifest,
    ToolPackageMetadata,
    ToolPackageSpec,
)
from nexus_ai_engine.contracts.tool_request import ToolResponseStatus
from nexus_ai_engine.executor.tool_dispatcher import ToolDispatcher
from nexus_ai_engine.registry.registry import ToolRegistry


TENANT = uuid4()
EXEC_ID = uuid4()


def _o2c_manifest() -> ToolPackageManifest:
    return ToolPackageManifest(
        metadata=ToolPackageMetadata(
            id="test-o2c",
            version="1.0.0",
            domain="o2c",
            publisher="test",
        ),
        spec=ToolPackageSpec(
            ontology_api=OntologyApiSpec(
                vdl_base_url="http://ontology/api/v1/vdl",
                connector_base_url="http://ontology/api/v1/connectors",
            ),
            tools=[
                ToolPackageEntry(
                    tool_id="mock",
                    version="0.1.0",
                    module="nexus_ai_engine.tools.base.mock:MockTool",
                )
            ],
        ),
    )


@pytest.mark.asyncio
async def test_dispatcher_uses_registry_tool_with_runtime():
    registry = ToolRegistry()
    registry.load_package(_o2c_manifest())
    tool = registry.get("mock")
    tool.expect("nexus-ai", {"ok": True})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={"virtualEntity": "X", "rows": []})
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    dispatcher = ToolDispatcher(registry=registry, _http=http)
    req = dispatcher.build_request(
        tool_id="mock",
        arguments={"payload": {"x": 1}},
        tenant_id=TENANT,
        trace_id="t1",
        execution_id=EXEC_ID,
        node_id=uuid4(),
        attempt=1,
        capability="nexus-ai",
    )
    resp = await dispatcher.dispatch(req)
    await dispatcher.aclose()
    assert resp.status is ToolResponseStatus.OK
    assert resp.result == {"ok": True}


@pytest.mark.asyncio
async def test_dispatcher_forwards_tenant_headers():
    manifest = ToolPackageManifest(
        metadata=ToolPackageMetadata(id="o2c-hdr", version="1.0.0", domain="o2c", publisher="test"),
        spec=ToolPackageSpec(
            ontology_api=OntologyApiSpec(
                vdl_base_url="http://ontology/api/v1/vdl",
                connector_base_url="http://ontology/api/v1/connectors",
            ),
            tools=[
                ToolPackageEntry(
                    tool_id="o2c_match_order_delivery_invoice",
                    version="1.0.0",
                    module="o2c_tools.match:O2cMatchOrderDeliveryInvoiceTool",
                )
            ],
        ),
    )
    registry = ToolRegistry()
    registry.load_package(manifest)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["tenant"] = request.headers.get("X-Nexus-Tenant-Id")
        captured["trace"] = request.headers.get("X-Nexus-Trace-Id")
        body = json.loads(request.content)
        entity = body["virtualEntity"]
        return httpx.Response(200, json={"virtualEntity": entity, "rows": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    dispatcher = ToolDispatcher(registry=registry, _http=http)
    req = dispatcher.build_request(
        tool_id="o2c_match_order_delivery_invoice",
        arguments={"opportunity_id": "OPP-1"},
        tenant_id=TENANT,
        trace_id="trace-forward",
        execution_id=EXEC_ID,
        node_id=uuid4(),
        attempt=1,
    )
    await dispatcher.dispatch(req)
    await dispatcher.aclose()
    assert captured["tenant"] == str(TENANT)
    assert captured["trace"] == "trace-forward"


@pytest.mark.asyncio
async def test_dispatcher_falls_back_to_embedded():
    dispatcher = ToolDispatcher(registry=ToolRegistry())
    req = dispatcher.build_request(
        tool_id="echo",
        arguments={"message": "hi"},
        tenant_id=TENANT,
        trace_id="t2",
        execution_id=EXEC_ID,
        node_id=uuid4(),
        attempt=1,
    )
    resp = await dispatcher.dispatch(req)
    assert resp.status is ToolResponseStatus.OK
    assert resp.result["message"] == "hi"
