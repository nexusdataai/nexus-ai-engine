"""Golden compile tests for example Journey DSL YAML files."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import yaml

from nexus_ai_engine.contracts.execution_graph import ExecutionGraph
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.journeys.compiler import JourneyCompiler
from nexus_ai_engine.journeys.validator import JourneyValidator

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"
GOLDEN = Path(__file__).resolve().parent / "golden" / "execution_graphs"


def _load(name: str) -> JourneyDefinition:
    raw = yaml.safe_load((EXAMPLES / name).read_text(encoding="utf-8"))
    assert JourneyValidator().validate(raw).valid
    return JourneyDefinition.model_validate(raw)


def test_compiler_produces_valid_execution_graph_for_order_to_cash():
    journey = _load("order-to-cash.yaml")
    graph = JourneyCompiler().compile(journey, tenant_id=uuid4())
    assert isinstance(graph, ExecutionGraph)
    assert len(graph.nodes) >= 5
    assert graph.content_sha256
    tool_nodes = [n for n in graph.nodes if n.tool_id]
    assert any(n.tool_id == "query_virtual_entity" for n in tool_nodes)


def test_compiler_is_deterministic_for_content_sha_inputs():
    journey = _load("order-to-cash.yaml")
    tenant = uuid4()
    g1 = JourneyCompiler().compile(journey, tenant_id=tenant, trace_id="t")
    g2 = JourneyCompiler().compile(journey, tenant_id=tenant, trace_id="t")
    assert len(g1.nodes) == len(g2.nodes)
    # node ids differ (uuid4) but node count and kinds match
    assert [n.kind for n in g1.nodes] == [n.kind for n in g2.nodes]


def test_golden_node_counts_match_snapshot():
    journey = _load("order-to-cash.yaml")
    graph = JourneyCompiler().compile(journey, tenant_id=uuid4())
    golden_path = GOLDEN / "order-to-cash.nodes.json"
    if not golden_path.exists():
        import json

        GOLDEN.mkdir(parents=True, exist_ok=True)
        payload = {
            "node_count": len(graph.nodes),
            "kinds": [n.kind.value for n in graph.nodes],
            "tool_ids": [n.tool_id for n in graph.nodes if n.tool_id],
        }
        golden_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    import json

    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert len(graph.nodes) == expected["node_count"]
    assert [n.kind.value for n in graph.nodes] == expected["kinds"]
