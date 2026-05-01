"""Unit tests for nexus_ai_engine.config.EngineConfig."""

from __future__ import annotations

import dataclasses

import pytest

from nexus_ai_engine.config import EngineConfig


def test_defaults_are_conservative() -> None:
    cfg = EngineConfig()
    assert cfg.region is None
    assert cfg.role_arn is None
    assert cfg.dynamodb_transformation_table is None
    assert cfg.dynamodb_prompts_table is None
    assert cfg.s3_journey_logs_bucket is None
    assert cfg.s3_journey_reports_bucket is None
    assert cfg.max_concurrent_jobs == 10
    assert cfg.job_task_cleanup_interval_seconds == 60
    assert cfg.extras == {}


def test_frozen() -> None:
    cfg = EngineConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.region = "us-east-1"  # type: ignore[misc]


def test_equality_by_value() -> None:
    a = EngineConfig(region="us-east-1", max_concurrent_jobs=4)
    b = EngineConfig(region="us-east-1", max_concurrent_jobs=4)
    assert a == b


def test_extras_independence_across_instances() -> None:
    a = EngineConfig()
    b = EngineConfig()
    a.extras["hint"] = 1
    assert "hint" not in b.extras


def test_positive_concurrency() -> None:
    cfg = EngineConfig(max_concurrent_jobs=1)
    assert cfg.max_concurrent_jobs == 1


def test_accepts_explicit_extras() -> None:
    cfg = EngineConfig(extras={"feature_flag_x": True})
    assert cfg.extras == {"feature_flag_x": True}
