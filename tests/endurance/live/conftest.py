"""Fixtures for live-cluster endurance (skipped when ENDURANCE_BASE_URL unset)."""

from __future__ import annotations

import os

import pytest

from .soak_runner import BulkRunSoakRunner


@pytest.fixture(scope="session")
def endurance_base_url() -> str:
    url = os.getenv("ENDURANCE_BASE_URL", "").strip()
    if not url:
        pytest.skip("ENDURANCE_BASE_URL not set — skip live endurance")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def bulk_run_soak_runner(endurance_base_url: str) -> BulkRunSoakRunner:
    return BulkRunSoakRunner(endurance_base_url)
