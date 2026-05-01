"""Root conftest — library-wide fixtures used across all tiers.

The harness entry point (``nexus_ai_engine.testing.fixtures``) already
provides ``engine_config``, ``engine``, ``app``, ``http_client``,
``mcp_client``, ``journey_runner``. This file intentionally keeps that
inventory authoritative and only layers on things the harness can't know
about (e.g. sample-data locators).
"""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = TESTS_DIR / "journeys" / "samples"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR
