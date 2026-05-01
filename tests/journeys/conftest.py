"""Journeys-tier fixtures — sample YAML locators and dedicated runner."""

from __future__ import annotations

from pathlib import Path

import pytest

JOURNEYS_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = JOURNEYS_DIR / "samples"


@pytest.fixture
def journey_samples_dir() -> Path:
    return SAMPLES_DIR


@pytest.fixture(params=sorted(p.name for p in SAMPLES_DIR.glob("*.yaml")))
def sample_journey_path(request: pytest.FixtureRequest) -> Path:
    return SAMPLES_DIR / request.param
