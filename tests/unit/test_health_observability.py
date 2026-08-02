"""Unit tests for readiness and metrics helpers."""

from __future__ import annotations

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.server.observability import build_metrics_registry, git_sha
from nexus_ai_engine.server.routers.health import readiness_payload
from nexus_ai_engine.testing.factory import make_test_engine


def test_readiness_payload_ready_with_engine() -> None:
    engine = make_test_engine()
    body, ready = readiness_payload(engine)
    assert ready is True
    assert body["checks"]["engine"]["status"] == "ok"
    assert body["checks"]["tool_registry"]["status"] == "ok"
    assert body["checks"]["dynamodb"]["status"] == "skipped"


def test_readiness_payload_not_ready_without_engine() -> None:
    body, ready = readiness_payload(None)
    assert ready is False
    assert body["checks"]["engine"]["status"] == "unavailable"


def test_readiness_dynamodb_skipped_for_in_memory_engine() -> None:
    engine = InMemoryEngine()
    body, _ = readiness_payload(engine)
    assert body["checks"]["dynamodb"]["status"] == "skipped"
    assert body["checks"]["dynamodb"]["reason"] == "in_memory_engine"


def test_build_metrics_registry_exposes_build_info() -> None:
    from prometheus_client import generate_latest

    registry = build_metrics_registry()
    output = generate_latest(registry).decode()
    assert "nexus_ai_engine_build_info" in output


def test_git_sha_defaults_to_unknown(monkeypatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILD_GIT_SHA", raising=False)
    monkeypatch.delenv("SOURCE_VERSION", raising=False)
    assert git_sha() == "unknown"
