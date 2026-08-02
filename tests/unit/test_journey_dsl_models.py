"""Unit tests for Journey DSL Pydantic models (spec 010)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nexus_ai_engine.contracts.journey_dsl import (
    Journey,
    JourneyDefinition,
    JourneyStep,
    JourneyTrigger,
    RiskClass,
    StepKind,
    walk_steps,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"


def test_public_aliases():
    assert Journey is JourneyDefinition


def test_compute_step_accepts_logic():
    step = JourneyStep(id="transform", type=StepKind.COMPUTE, logic="$.items | length")
    assert step.logic == "$.items | length"


def test_walk_steps_includes_nested_parallel():
    parent = JourneyStep(
        id="parallel_fetch",
        parallel=True,
        steps=[
            JourneyStep(id="fetch_a", tool="echo"),
            JourneyStep(id="fetch_b", tool="echo"),
        ],
    )
    ids = [s.id for s in walk_steps([parent])]
    assert ids == ["parallel_fetch", "fetch_a", "fetch_b"]


@pytest.mark.parametrize(
    "filename",
    ["order-to-cash.yaml"],
)
def test_example_dsl_yaml_parses(filename: str):
    raw = yaml.safe_load((EXAMPLES / filename).read_text(encoding="utf-8"))
    journey = JourneyDefinition.model_validate(raw)
    assert journey.metadata.id == "order-to-cash-monitor"
    assert journey.spec.trigger is JourneyTrigger.MANUAL
    assert len(journey.spec.stages) == 3


def test_spec_minimal_journey():
    data = {
        "apiVersion": "nexus.ai/v1",
        "kind": "Journey",
        "metadata": {"id": "hello-tool", "version": 1},
        "spec": {
            "display_name": "Hello Tool",
            "stages": [
                {
                    "id": "main",
                    "steps": [
                        {
                            "id": "ping",
                            "tool": "query_virtual_entity",
                            "params": {"entity": "HealthCheck", "limit": 1},
                        }
                    ],
                }
            ],
        },
    }
    journey = JourneyDefinition.model_validate(data)
    assert journey.spec.stages[0].steps[0].tool == "query_virtual_entity"


def test_write_step_risk_class():
    raw = yaml.safe_load((EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8"))
    journey = JourneyDefinition.model_validate(raw)
    write_step = journey.spec.stages[1].steps[1]
    assert write_step.risk_class is RiskClass.WRITE
    assert write_step.requires_approval is True
