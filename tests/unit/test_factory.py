"""Unit tests for build_engine — now returns a live InMemoryEngine."""

from __future__ import annotations

from nexus_ai_engine.config import EngineConfig
from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.factory import build_engine


def test_build_engine_returns_in_memory_engine() -> None:
    engine = build_engine(EngineConfig())
    assert isinstance(engine, InMemoryEngine)


def test_build_engine_seeds_demo_journeys_by_default() -> None:
    engine = build_engine(EngineConfig())
    assert len(engine.journeys) >= 5
    names = {j.name for j in engine.journeys.values()}
    assert "Order-to-Cash Monitor" in names
    assert "Call Processing Pipeline" in names


def test_build_engine_seed_demo_can_be_disabled() -> None:
    engine = build_engine(EngineConfig(), seed_demo=False)
    assert engine.journeys == {}
    assert engine.schedules == {}
