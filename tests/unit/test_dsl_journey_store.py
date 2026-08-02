"""Tests for DslJourneyStore."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.journeys.service import DslJourneyStore, JourneyVersionConflictError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"


def _sample() -> JourneyDefinition:
    raw = yaml.safe_load((EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8"))
    return JourneyDefinition.model_validate(raw)


def test_create_and_list_versions():
    store = DslJourneyStore()
    definition = _sample()
    store.create(definition)
    assert store.list_versions("order-to-cash-monitor") == [1]
    assert store.get("order-to-cash-monitor") is not None


def test_published_version_is_immutable():
    store = DslJourneyStore()
    definition = _sample()
    store.create(definition, publish=True)
    with pytest.raises(JourneyVersionConflictError):
        store.create(definition, publish=True)


def test_export_yaml_round_trip():
    store = DslJourneyStore()
    definition = _sample()
    store.create(definition)
    exported = store.export_yaml("order-to-cash-monitor")
    again = JourneyDefinition.model_validate(yaml.safe_load(exported))
    assert again.metadata.id == definition.metadata.id
    assert again.spec.display_name == definition.spec.display_name
