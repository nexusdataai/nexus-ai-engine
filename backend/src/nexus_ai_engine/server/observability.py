"""Prometheus metrics registry for the reference server."""

from __future__ import annotations

import os

from prometheus_client import CollectorRegistry, Gauge

from .. import __version__
from ..config import get_config


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
    return registry


def git_sha() -> str:
    return (
        os.getenv("GIT_SHA")
        or os.getenv("BUILD_GIT_SHA")
        or os.getenv("SOURCE_VERSION")
        or "unknown"
    )
