"""Contract round-trip and validation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import yaml

from nexus_ai_engine.contracts.execution_graph import (
    ExecutionGraph,
    ExecutionNode,
    NodeKind,
)
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.contracts.tool_request import (
    ToolRequest,
    ToolRequestMode,
    ToolResponse,
    ToolResponseStatus,
)


def _minimal_journey_dict() -> dict:
    return {
        "apiVersion": "nexus.ai/v1",
        "kind": "Journey",
        "metadata": {
            "id": "hello-tool",
            "version": 1,
        },
        "spec": {
            "display_name": "Hello Tool",
            "stages": [
                {
                    "id": "main",
                    "steps": [
                        {
                            "id": "say_hello",
                            "tool": "query_virtual_entity",
                            "params": {"entity": "Opportunity", "limit": 5},
                        }
                    ],
                }
            ],
        },
    }


def test_journey_definition_round_trip_json():
    data = _minimal_journey_dict()
    journey = JourneyDefinition.model_validate(data)
    dumped = journey.model_dump(by_alias=True)
    again = JourneyDefinition.model_validate(dumped)
    assert again.metadata.id == "hello-tool"
    assert again.spec.stages[0].steps[0].tool == "query_virtual_entity"


def test_journey_definition_from_yaml():
    raw = yaml.safe_dump(_minimal_journey_dict())
    data = yaml.safe_load(raw)
    journey = JourneyDefinition.model_validate(data)
    assert journey.kind == "Journey"


def test_journey_rejects_duplicate_step_ids():
    data = _minimal_journey_dict()
    data["spec"]["stages"][0]["steps"].append(
        {"id": "say_hello", "tool": "other_tool", "params": {}}
    )
    with pytest.raises(ValueError, match="duplicate step id"):
        JourneyDefinition.model_validate(data)


def test_journey_schedule_requires_cron():
    data = _minimal_journey_dict()
    data["spec"]["trigger"] = "schedule"
    with pytest.raises(ValueError, match="schedule is required"):
        JourneyDefinition.model_validate(data)


def test_execution_graph_dag_validation():
    n1 = uuid4()
    n2 = uuid4()
    now = datetime.now(timezone.utc)
    tenant = uuid4()
    planner = uuid4()
    nodes = [
        ExecutionNode(
            node_id=n1,
            kind=NodeKind.TOOL_CALL,
            tool_id="query_virtual_entity",
            capability="nexus-ai",
        ),
        ExecutionNode(
            node_id=n2,
            kind=NodeKind.TOOL_CALL,
            tool_id="other_tool",
            capability="nexus-ai",
            depends_on=[n1],
        ),
    ]
    content_sha = ExecutionGraph.compute_content_sha256(nodes, [], 4, 3600)
    graph = ExecutionGraph(
        id=uuid4(),
        version=1,
        created_at=now,
        tenant_id=tenant,
        trace_id="trace-1",
        planner_result_id=planner,
        nodes=nodes,
        content_sha256=content_sha,
    )
    assert len(graph.nodes) == 2


def test_execution_graph_rejects_cycle():
    n1, n2 = uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    nodes = [
        ExecutionNode(
            node_id=n1,
            kind=NodeKind.TOOL_CALL,
            tool_id="a",
            capability="nexus-ai",
            depends_on=[n2],
        ),
        ExecutionNode(
            node_id=n2,
            kind=NodeKind.TOOL_CALL,
            tool_id="b",
            capability="nexus-ai",
            depends_on=[n1],
        ),
    ]
    with pytest.raises(ValueError, match="cycle"):
        ExecutionGraph(
            id=uuid4(),
            version=1,
            created_at=now,
            tenant_id=uuid4(),
            trace_id="t",
            planner_result_id=uuid4(),
            nodes=nodes,
            content_sha256="0" * 64,
        )


def test_tool_request_response_round_trip():
    now = datetime.now(timezone.utc)
    tenant = uuid4()
    req_id = uuid4()
    exec_id = uuid4()
    node_id = uuid4()
    planner_id = uuid4()
    request = ToolRequest(
        id=req_id,
        version=1,
        created_at=now,
        tenant_id=tenant,
        trace_id="trace-1",
        tool_id="query_virtual_entity",
        tool_version="1.0.0",
        capability="nexus-ai",
        mode=ToolRequestMode.READ,
        idempotency_key="exec:node:1",
        caller_execution_id=exec_id,
        caller_node_id=node_id,
        caller_planner_result_id=planner_id,
    )
    payload = request.model_dump(mode="json")
    again = ToolRequest.model_validate(payload)
    assert again.tool_id == "query_virtual_entity"

    response = ToolResponse(
        id=uuid4(),
        version=1,
        created_at=now,
        tenant_id=tenant,
        trace_id="trace-1",
        request_id=req_id,
        tool_id="query_virtual_entity",
        tool_version="1.0.0",
        capability="nexus-ai",
        status=ToolResponseStatus.OK,
        started_at=now,
        ended_at=now,
        duration_ms=42,
    )
    resp_payload = response.model_dump(mode="json")
    assert ToolResponse.model_validate(resp_payload).status is ToolResponseStatus.OK


def test_export_cli_writes_schemas(tmp_path):
    from nexus_ai_engine.contracts.export import export_all

    written = export_all(tmp_path)
    assert len(written) == 4
    names = {p.name for p in written}
    assert "journey-dsl-v1.schema.json" in names
    assert "execution-graph.schema.json" in names
