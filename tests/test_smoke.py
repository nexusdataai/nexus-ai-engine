"""Smoke tests — ensure the package imports and exposes its version."""

from __future__ import annotations

import nexus_ai_engine
from nexus_ai_engine.config import EngineConfig
from nexus_ai_engine.errors import (
    ConfigurationError,
    EngineError,
    JobCancelledError,
    RepositoryError,
    StageNotRegisteredError,
)


def test_version_exposed() -> None:
    assert isinstance(nexus_ai_engine.__version__, str)
    assert nexus_ai_engine.__version__.startswith("0.1.")


def test_engine_config_defaults() -> None:
    cfg = EngineConfig()
    assert cfg.max_concurrent_jobs == 10
    assert cfg.job_task_cleanup_interval_seconds == 60
    assert cfg.extras == {}


def test_engine_config_is_frozen() -> None:
    cfg = EngineConfig()
    try:
        cfg.region = "us-east-1"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("EngineConfig should be frozen")


def test_error_hierarchy() -> None:
    for cls in (ConfigurationError, StageNotRegisteredError, JobCancelledError, RepositoryError):
        assert issubclass(cls, EngineError)


def test_submodules_importable() -> None:
    import nexus_ai_engine.adapters  # noqa: F401
    import nexus_ai_engine.contracts  # noqa: F401
    import nexus_ai_engine.events  # noqa: F401
    import nexus_ai_engine.execution  # noqa: F401
    import nexus_ai_engine.models  # noqa: F401
    import nexus_ai_engine.services  # noqa: F401
    import nexus_ai_engine.stages  # noqa: F401
