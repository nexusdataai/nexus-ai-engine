"""Unit tests for settings overrides and payload shape."""

from __future__ import annotations

import os

from nexus_ai_engine.services.job_execution_config_service import (
    JobExecutionConfigService,
    get_job_execution_config,
)
from nexus_ai_engine.services.settings_service import get_settings


def test_apply_overrides_clamps_threads_and_global_jobs(monkeypatch) -> None:
    monkeypatch.delenv("JOB_WORKER_THREADS", raising=False)
    monkeypatch.delenv("MAX_GLOBAL_JOBS", raising=False)
    cfg = JobExecutionConfigService()
    applied = cfg.apply_overrides(worker_threads=99, max_global_jobs=0)
    assert applied["worker_threads"] == 16
    assert applied["max_global_jobs"] == 1
    assert cfg.get_worker_threads() == 16
    assert cfg.get_max_global_jobs() == 1
    os.environ.pop("JOB_WORKER_THREADS", None)
    os.environ.pop("MAX_GLOBAL_JOBS", None)


def test_get_settings_includes_worker_queue_scheduler_version() -> None:
    payload = get_settings()
    assert {"workers", "queue", "scheduler", "version"} <= set(payload)
    assert payload["workers"]["threads_min"] == 1
    assert payload["workers"]["threads_max"] == 16
    assert payload["queue"]["max_global_jobs_cap"] == 50
    assert payload["version"]["name"] == "nexus-ai-engine"
    assert payload["version"]["version"]
    get_job_execution_config()  # singleton stays usable
