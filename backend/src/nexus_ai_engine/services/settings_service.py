"""Aggregate and update Journey Studio runtime settings."""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from ..config import get_config
from ..runtime_version import deployed_git_sha, deployed_version
from .job_execution_config_service import (
    MAX_MAX_GLOBAL_JOBS,
    MAX_WORKER_THREADS,
    MIN_MAX_GLOBAL_JOBS,
    MIN_WORKER_THREADS,
    get_job_execution_config,
)
from .job_queue_service import JOB_CONSUMER_GROUP, JOB_STREAM_KEY, is_queue_mode, redis_available
from .worker_management_service import get_worker_management_service


def get_settings() -> Dict[str, Any]:
    cfg = get_job_execution_config()
    workers = get_worker_management_service().get_summary()
    scheduler = _scheduler_status()
    engine = get_config()
    return {
        "workers": {
            "replicas": workers.get("replicas"),
            "desired": (workers.get("deployment") or {}).get("desired"),
            "ready": (workers.get("deployment") or {}).get("ready"),
            "max_replicas": workers.get("max_worker_replicas"),
            "threads": cfg.get_worker_threads(),
            "threads_min": MIN_WORKER_THREADS,
            "threads_max": MAX_WORKER_THREADS,
            "k8s_available": workers.get("k8s_available"),
            "autoscaling": workers.get("autoscaling"),
        },
        "queue": {
            "mode": "queue" if is_queue_mode() else "inline",
            "redis_available": redis_available(),
            "max_global_jobs": cfg.get_max_global_jobs(),
            "min_global_jobs": MIN_MAX_GLOBAL_JOBS,
            "max_global_jobs_cap": MAX_MAX_GLOBAL_JOBS,
            "stream_key": JOB_STREAM_KEY,
            "consumer_group": JOB_CONSUMER_GROUP,
        },
        "scheduler": scheduler,
        "version": {
            "name": "nexus-ai-engine",
            "version": deployed_version(),
            "env": engine.environment,
            "git_sha": deployed_git_sha(),
        },
    }


def update_settings(
    *,
    replicas: Optional[int] = None,
    worker_threads: Optional[int] = None,
    max_global_jobs: Optional[int] = None,
    scheduler_interval_sec: Optional[int] = None,
    autoscaling: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    notes: list[str] = []
    cfg = get_job_execution_config()
    worker_svc = get_worker_management_service()

    env_updates: Dict[str, str] = {}
    applied = cfg.apply_overrides(worker_threads=worker_threads, max_global_jobs=max_global_jobs)
    if "worker_threads" in applied:
        env_updates["JOB_WORKER_THREADS"] = str(applied["worker_threads"])
        notes.append("Threads apply after worker pods roll.")
    if "max_global_jobs" in applied:
        env_updates["MAX_GLOBAL_JOBS"] = str(applied["max_global_jobs"])
        notes.append("Global job cap updated in this API process.")

    if replicas is not None:
        worker_svc.scale_workers(int(replicas))
        notes.append("Worker replica count updated.")

    if autoscaling is not None:
        worker_svc.configure_autoscaling(
            enabled=bool(autoscaling.get("enabled")),
            min_replicas=int(autoscaling.get("min_replicas", 1)),
            max_replicas=int(autoscaling.get("max_replicas", 10)),
            lag_threshold=int(autoscaling.get("lag_threshold", 5)),
        )
        notes.append("Autoscaling updated (two-wave drain).")
    elif worker_svc.k8s_available and ("worker_threads" in applied or "max_global_jobs" in applied):
        try:
            if worker_svc.sync_two_wave_autoscaling():
                notes.append("Autoscaling target refreshed for thread or global-cap change.")
        except Exception as exc:
            logger.warning("Two-wave autoscaling refresh skipped: {}", exc)

    if env_updates and worker_svc.k8s_available:
        try:
            worker_svc.patch_worker_env(env_updates)
            notes.append("Worker deployment env patched; pods will restart.")
        except Exception as exc:
            logger.warning("Worker env patch skipped: {}", exc)
            notes.append(f"Worker env patch skipped: {exc}")

    if scheduler_interval_sec is not None:
        try:
            from .scheduler_service import SchedulerService

            interval = SchedulerService.get_instance().set_check_interval(int(scheduler_interval_sec))
            notes.append(f"Scheduler check interval set to {interval}s.")
        except Exception as exc:
            logger.warning("Scheduler interval update skipped: {}", exc)
            notes.append(f"Scheduler interval update skipped: {exc}")

    result = get_settings()
    result["notes"] = notes
    return result


def _scheduler_status() -> Dict[str, Any]:
    fallback = {
        "running": False,
        "schedule_count": 0,
        "enabled_count": 0,
        "check_interval_sec": 30,
    }
    try:
        from .scheduler_service import SchedulerService

        inst = SchedulerService._instance
        if inst is None:
            return fallback
        return inst.get_status()
    except Exception:
        return fallback
