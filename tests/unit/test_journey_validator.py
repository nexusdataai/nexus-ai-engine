"""Tests for JourneyValidator."""

from __future__ import annotations

from pathlib import Path

import yaml

from nexus_ai_engine.journeys.validator import JourneyValidator

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"


def test_validate_accepts_order_to_cash_sample():
    raw = yaml.safe_load((EXAMPLES / "order-to-cash.yaml").read_text(encoding="utf-8"))
    result = JourneyValidator().validate(raw)
    assert result.valid, result.errors


def test_validate_rejects_invalid_dsl():
    result = JourneyValidator().validate(
        {
            "apiVersion": "nexus.ai/v1",
            "kind": "Journey",
            "metadata": {"id": "bad id spaces", "version": 1},
            "spec": {"display_name": "x", "stages": []},
        }
    )
    assert not result.valid
    assert len(result.errors) >= 1


def test_validate_warns_unknown_tool():
    result = JourneyValidator().validate(
        {
            "apiVersion": "nexus.ai/v1",
            "kind": "Journey",
            "metadata": {"id": "warn-test", "version": 1},
            "spec": {
                "display_name": "Warn",
                "stages": [
                    {
                        "id": "main",
                        "steps": [{"id": "step_a", "tool": "totally_unknown_tool_xyz"}],
                    }
                ],
            },
        }
    )
    assert result.valid
    assert any(w.code == "unknown_tool" for w in result.warnings)


def test_strict_tools_makes_unknown_tool_an_error():
    result = JourneyValidator().validate(
        {
            "apiVersion": "nexus.ai/v1",
            "kind": "Journey",
            "metadata": {"id": "strict-test", "version": 1},
            "spec": {
                "display_name": "Strict",
                "stages": [
                    {
                        "id": "main",
                        "steps": [{"id": "step_a", "tool": "totally_unknown_tool_xyz"}],
                    }
                ],
            },
        },
        strict_tools=True,
    )
    assert not result.valid
