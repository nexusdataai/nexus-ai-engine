"""Unit tests for the bundled demo stage implementations.

Covers shape contracts on ``DEMO_JOURNEYS``, the registration helper,
and the per-step execution behaviour. AWS interactions are mocked so the
tests run without moto / boto3 — the integration test exercises the
real ``BaseStage.__init__`` AWS client wiring under ``@moto.mock_aws``.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from nexus_ai_engine.stages import (
    DEMO_JOURNEYS,
    DemoStage,
    list_demo_stage_ids,
    register_demo_stages,
)
from nexus_ai_engine.stages.demo import _make_demo_stage_class
from nexus_ai_engine.stages.registry import (
    STAGE_REGISTRY,
    clear_registry,
    get_stage_class,
    list_available_stages,
)


# ── DEMO_JOURNEYS shape contract ───────────────────────────────────────


def test_demo_journeys_count_and_names() -> None:
    """Core journeys stay first; the supply-chain load set brings the catalog to 50+."""
    names = [j["name"] for j in DEMO_JOURNEYS]
    assert names[:5] == [
        "Order-to-Cash Monitor",
        "Call Processing Pipeline",
        "Demand Forecasting Engine",
        "Inventory Optimization",
        "Supply Chain Risk",
    ]
    assert len(names) >= 50
    assert len(names) == len(set(names))


def test_every_journey_has_required_fields() -> None:
    valid_oda = {
        "customer-management", "product-management", "order-management",
        "billing-management", "payment-management", "inventory-management",
        "party-management", "resource-management", "service-management",
        "data-pipeline",
        "risk-management",
    }
    for j in DEMO_JOURNEYS:
        assert {"name", "description", "odaComponentType", "stages"} <= set(j)
        assert j["odaComponentType"] in valid_oda, j["odaComponentType"]
        assert isinstance(j["stages"], list) and j["stages"]
        for s in j["stages"]:
            assert {"stage_id", "name", "steps"} <= set(s)
            assert isinstance(s["steps"], list) and s["steps"]
            for step in s["steps"]:
                assert {"id", "name"} <= set(step)


def test_step_ids_unique_within_each_stage() -> None:
    """Step IDs must be unique within a stage (executor uses them as keys)."""
    for j in DEMO_JOURNEYS:
        for s in j["stages"]:
            ids = [step["id"] for step in s["steps"]]
            assert len(ids) == len(set(ids)), (
                f"duplicate step_id in stage {s['stage_id']}: {ids}"
            )


def test_stage_ids_unique_globally() -> None:
    """Stage IDs must be unique across all demo journeys — the registry
    is keyed on stage_id and the second registration would silently
    shadow the first."""
    ids = list_demo_stage_ids()
    assert len(ids) == len(set(ids)), f"duplicate demo stage_id: {ids}"


# ── register_demo_stages ───────────────────────────────────────────────


def test_register_demo_stages_populates_registry() -> None:
    clear_registry()
    try:
        registered = register_demo_stages()
        assert registered == list_demo_stage_ids()
        # Every registered stage_id resolves to a DemoStage subclass.
        for sid in registered:
            cls = get_stage_class(sid)
            assert issubclass(cls, DemoStage), f"{sid} → {cls.__name__}"
            assert cls.__name__ == f"DemoStage_{sid}"
        assert sorted(list_available_stages()) == sorted(registered)
    finally:
        clear_registry()


def test_register_demo_stages_idempotent() -> None:
    """Calling twice shouldn't double-register — the second call replaces
    the first per the registry's dict-set semantics."""
    clear_registry()
    try:
        first = register_demo_stages()
        second = register_demo_stages()
        assert first == second
        assert sorted(list_available_stages()) == sorted(first)
    finally:
        clear_registry()


def test_register_demo_stages_uses_injected_register() -> None:
    """The ``registry_register`` arg lets tests intercept registration
    without touching the global STAGE_REGISTRY."""
    sink: List[tuple] = []

    def _capture(stage_id: str, cls: type) -> None:
        sink.append((stage_id, cls))

    register_demo_stages(registry_register=_capture)
    assert [s for s, _ in sink] == list_demo_stage_ids()


# ── DemoStage.execute_step behaviour ───────────────────────────────────


def _make_stage_for_test(steps: List[Dict[str, Any]]) -> DemoStage:
    """Construct a DemoStage subclass with mocked BaseStage AWS clients
    so we can exercise execute_step without moto."""
    cls = _make_demo_stage_class(
        stage_id="test_stage",
        stage_name="Test Stage",
        stage_description="Stage for unit-testing DemoStage.execute_step",
        step_definitions=steps,
    )
    # Patch BaseStage.__init__ to skip AWSClientManager construction; we
    # only need stage_log to capture into a list.
    with patch.object(DemoStage, "__init__", lambda self, *a, **kw: None):
        s = cls()
    s.journey_id = "JRN-TEST"
    s.stage_id = "test_stage"
    s.job_id = "JOB-TEST"
    s.logs = []
    s.metrics = {}
    s.artifacts = {}
    s._sse_emit_log = None
    s._local_logger = None
    s._last_db_cancel_check = {}
    # is_cancelled would otherwise hit DynamoDB; short-circuit it.
    s.is_cancelled = lambda: False  # type: ignore[method-assign]
    # stage_log writes to file/dynamo/SSE; replace with an in-memory capture.
    captured: List[Dict[str, str]] = []
    def _stage_log(level: str, message: str, step_id: str = None) -> None:
        captured.append({"level": level, "message": message, "step_id": step_id})
    s.stage_log = _stage_log  # type: ignore[method-assign]
    s._captured_logs = captured  # type: ignore[attr-defined]
    return s


def test_execute_step_completes_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nexus_ai_engine.stages.demo.time.sleep", lambda *_: None)
    s = _make_stage_for_test([
        {"id": "step-a", "name": "Step A", "ticks": 3,
         "sleep_min": 0.0, "sleep_max": 0.0},
    ])
    result = s.execute_step("step-a", {"id": "step-a", "name": "Step A"})

    assert result["status"] == "success"
    assert result["ticks_completed"] == 3
    assert result["items_processed"] > 0
    captured = s._captured_logs  # type: ignore[attr-defined]
    # Starting + 3 tick lines + Completed = 5 entries.
    assert len(captured) == 5
    levels = [c["level"] for c in captured]
    assert levels.count("INFO") == 5
    assert all(c["step_id"] == "step-a" for c in captured)


def test_execute_step_with_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nexus_ai_engine.stages.demo.time.sleep", lambda *_: None)
    s = _make_stage_for_test([
        {"id": "step-fail", "name": "Step Fail", "ticks": 2,
         "sleep_min": 0.0, "sleep_max": 0.0,
         "fail": True, "fail_reason": "stress test"},
    ])
    with pytest.raises(RuntimeError, match="stress test"):
        s.execute_step("step-fail", {"id": "step-fail", "name": "Step Fail"})

    captured = s._captured_logs  # type: ignore[attr-defined]
    # Starting + 2 ticks + ERROR — no completion line.
    assert any(c["level"] == "ERROR" and c["message"] == "stress test" for c in captured)


def test_execute_step_unknown_step_returns_failed() -> None:
    s = _make_stage_for_test([{"id": "known", "name": "Known"}])
    result = s.execute_step("unknown", {"id": "unknown"})
    assert result["status"] == "failed"
    assert "unknown step" in result["error"]


def test_execute_step_observes_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nexus_ai_engine.stages.demo.time.sleep", lambda *_: None)
    s = _make_stage_for_test([
        {"id": "long", "name": "Long", "ticks": 10,
         "sleep_min": 0.0, "sleep_max": 0.0},
    ])
    # Cancel after the second tick.
    call_count = {"n": 0}
    def _is_cancelled() -> bool:
        call_count["n"] += 1
        return call_count["n"] >= 3
    s.is_cancelled = _is_cancelled  # type: ignore[method-assign]

    result = s.execute_step("long", {"id": "long", "name": "Long"})
    assert result["status"] == "cancelled"
    # Two ticks before cancellation observation.
    assert result["ticks_completed"] == 2


def test_demo_stage_steps_property_emits_serialisable_dicts() -> None:
    """The executor calls ``stage.steps`` once and iterates the dicts;
    each must have ``id`` and ``name`` keys."""
    s = _make_stage_for_test([
        {"id": "a", "name": "A", "description": "first"},
        {"id": "b", "name": "B"},
    ])
    steps = s.steps
    assert steps == [
        {"id": "a", "name": "A", "description": "first"},
        {"id": "b", "name": "B", "description": ""},
    ]
