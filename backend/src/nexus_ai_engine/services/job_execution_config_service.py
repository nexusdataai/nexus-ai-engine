"""Runtime configuration for inline vs queue job execution modes."""

from __future__ import annotations

import os
from typing import Literal, Optional, Tuple

from loguru import logger

ExecutionMode = Literal["inline", "queue"]
ConfigSource = Literal["env", "default"]

VALID_EXECUTION_MODES = ("inline", "queue")
DEFAULT_EXECUTION_MODE: ExecutionMode = "inline"
DEFAULT_MAX_GLOBAL_JOBS = 50
DEFAULT_WORKER_REPLICAS = 1
DEFAULT_LONG_RUNNING_JOB_MIN = 180
DEFAULT_WORKER_THREADS = 3
MIN_MAX_GLOBAL_JOBS = 1
MAX_MAX_GLOBAL_JOBS = 50
MIN_WORKER_REPLICAS = 0
MIN_WORKER_THREADS = 1
MAX_WORKER_THREADS = 16


class JobExecutionConfigService:
    """Reads job execution settings from environment (SSM optional via host bootstrap)."""

    def __init__(self) -> None:
        self._capability = os.getenv("CAPABILITY_NAME", "ai-engine")
        self._environment = os.getenv("ENVIRONMENT", "dev")
        self._max_worker_replicas = int(os.getenv("JOB_WORKER_MAX_REPLICAS", "10"))

    def _read_env(self, name: str, default: str) -> Tuple[str, ConfigSource]:
        env_map = {
            "execution-mode": ("JOB_EXECUTION_MODE", DEFAULT_EXECUTION_MODE),
            "max-global-jobs": ("MAX_GLOBAL_JOBS", str(DEFAULT_MAX_GLOBAL_JOBS)),
            "worker-replicas": ("JOB_WORKER_REPLICAS", str(DEFAULT_WORKER_REPLICAS)),
            "worker-threads": ("JOB_WORKER_THREADS", str(DEFAULT_WORKER_THREADS)),
            "long-running-job-min": ("STALE_JOB_LONG_RUNNING_MIN", str(DEFAULT_LONG_RUNNING_JOB_MIN)),
        }
        env_var, fallback = env_map[name]
        val = os.getenv(env_var)
        if val is not None and str(val).strip():
            return str(val).strip(), "env"
        return fallback, "default"

    def get_execution_mode(self) -> ExecutionMode:
        raw, _ = self._read_env("execution-mode", DEFAULT_EXECUTION_MODE)
        candidate = (raw or DEFAULT_EXECUTION_MODE).strip().lower()
        if candidate not in VALID_EXECUTION_MODES:
            logger.warning(
                "Invalid execution mode %r; falling back to %r",
                raw,
                DEFAULT_EXECUTION_MODE,
            )
            return DEFAULT_EXECUTION_MODE
        return candidate  # type: ignore[return-value]

    def get_max_global_jobs(self) -> int:
        raw, _ = self._read_env("max-global-jobs", str(DEFAULT_MAX_GLOBAL_JOBS))
        try:
            value = int(raw or DEFAULT_MAX_GLOBAL_JOBS)
        except (TypeError, ValueError):
            value = DEFAULT_MAX_GLOBAL_JOBS
        return max(MIN_MAX_GLOBAL_JOBS, min(MAX_MAX_GLOBAL_JOBS, value))

    def get_worker_replicas_desired(self) -> int:
        raw, _ = self._read_env("worker-replicas", str(DEFAULT_WORKER_REPLICAS))
        try:
            value = int(raw or DEFAULT_WORKER_REPLICAS)
        except (TypeError, ValueError):
            value = DEFAULT_WORKER_REPLICAS
        return max(MIN_WORKER_REPLICAS, min(self._max_worker_replicas, value))

    def get_worker_threads(self) -> int:
        raw, _ = self._read_env("worker-threads", str(DEFAULT_WORKER_THREADS))
        try:
            value = int(raw or DEFAULT_WORKER_THREADS)
        except (TypeError, ValueError):
            value = DEFAULT_WORKER_THREADS
        return max(MIN_WORKER_THREADS, min(MAX_WORKER_THREADS, value))

    def get_long_running_job_min(self) -> int:
        raw, _ = self._read_env("long-running-job-min", str(DEFAULT_LONG_RUNNING_JOB_MIN))
        try:
            value = int(raw or DEFAULT_LONG_RUNNING_JOB_MIN)
        except (TypeError, ValueError):
            value = DEFAULT_LONG_RUNNING_JOB_MIN
        return max(30, min(720, value))

    def is_queue_mode(self) -> bool:
        return self.get_execution_mode() == "queue"

    def apply_overrides(
        self,
        *,
        worker_threads: Optional[int] = None,
        max_global_jobs: Optional[int] = None,
    ) -> dict:
        """Update process env so subsequent reads pick up new values."""
        applied: dict = {}
        if worker_threads is not None:
            value = max(MIN_WORKER_THREADS, min(MAX_WORKER_THREADS, int(worker_threads)))
            os.environ["JOB_WORKER_THREADS"] = str(value)
            applied["worker_threads"] = value
        if max_global_jobs is not None:
            value = max(MIN_MAX_GLOBAL_JOBS, min(MAX_MAX_GLOBAL_JOBS, int(max_global_jobs)))
            os.environ["MAX_GLOBAL_JOBS"] = str(value)
            applied["max_global_jobs"] = value
        return applied


_service: Optional[JobExecutionConfigService] = None


def get_job_execution_config() -> JobExecutionConfigService:
    global _service
    if _service is None:
        _service = JobExecutionConfigService()
    return _service
