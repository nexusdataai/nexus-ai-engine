"""Prometheus metrics registry for the reference server."""

from __future__ import annotations

import os

from prometheus_client import CollectorRegistry, Gauge

from .. import __version__
from ..config import get_config

_fleet_gauges: dict[str, Gauge] | None = None


def build_metrics_registry() -> CollectorRegistry:
    """Create a per-process metrics registry with static build info."""
    registry = CollectorRegistry()
    config = get_config()
    Gauge(
        "nexus_ai_engine_build_info",
        "Nexus AI Engine build information",
        ["service", "version", "env"],
        registry=registry,
    ).labels(
        service="nexus-ai-engine",
        version=__version__,
        env=config.environment,
    ).set(1)
    global _fleet_gauges
    _fleet_gauges = {
        "active": Gauge(
            "nexus_ai_engine_executions_active",
            "Active in-flight executions",
            registry=registry,
        ),
        "queued": Gauge(
            "nexus_ai_engine_executions_queued",
            "Executions waiting to start",
            registry=registry,
        ),
        "failed": Gauge(
            "nexus_ai_engine_executions_failed",
            "Failed executions in current fleet snapshot",
            registry=registry,
        ),
        "workers": Gauge(
            "nexus_ai_engine_workers",
            "Reported worker count (API + lock holders)",
            registry=registry,
        ),
    }
    return registry


def update_fleet_gauges(summary: dict) -> None:
    """Refresh fleet gauges from /fleet/summary payload."""
    if _fleet_gauges is None:
        return
    _fleet_gauges["active"].set(summary.get("active", 0))
    _fleet_gauges["queued"].set(summary.get("queued", 0))
    _fleet_gauges["failed"].set(summary.get("failed", 0))
    _fleet_gauges["workers"].set(summary.get("workers", 0))


def git_sha() -> str:
    return (
        os.getenv("GIT_SHA")
        or os.getenv("BUILD_GIT_SHA")
        or os.getenv("SOURCE_VERSION")
        or "unknown"
    )
