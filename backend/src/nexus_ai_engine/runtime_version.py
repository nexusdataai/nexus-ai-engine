"""Deployed ai-engine version (single product version for About /health /version)."""

from __future__ import annotations

import os
from pathlib import Path

from . import __version__

_VERSION_FILES = (
    Path("/VERSION"),
    Path("/app/VERSION"),
)


def _raw_version() -> str:
    for key in ("APP_VERSION", "AI_ENGINE_VERSION", "VERSION"):
        value = (os.getenv(key) or "").strip()
        if value and value.lower() not in {"latest", "unknown", "0.0.0"}:
            return value
    for path in _VERSION_FILES:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return __version__


def deployed_version() -> str:
    """Semver currently deployed (image tag without git suffix)."""
    raw = _raw_version()
    if "-" in raw:
        head, tail = raw.rsplit("-", 1)
        if len(tail) >= 7 and all(c in "0123456789abcdef" for c in tail.lower()):
            return head
    return raw


def deployed_git_sha() -> str:
    for key in ("GIT_SHA", "BUILD_GIT_SHA", "BUILD_SHA", "SOURCE_VERSION"):
        value = (os.getenv(key) or "").strip()
        if value and value.lower() != "unknown":
            return value
    raw = _raw_version()
    if "-" in raw:
        tail = raw.rsplit("-", 1)[1]
        if len(tail) >= 7 and all(c in "0123456789abcdef" for c in tail.lower()):
            return tail
    return "unknown"
