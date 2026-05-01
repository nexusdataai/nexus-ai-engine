"""Exercise the sample journey YAMLs through the JourneyYAMLRunner.

Phase-1 behavior: every sample must parse and validate cleanly (status
``validated``). When the app fixture is wired, the runner instead reports
``pending_phase_9`` because the end-to-end path lands in phase 9.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nexus_ai_engine.testing import JourneyYAMLRunner


def test_all_samples_parse(sample_journey_path: Path) -> None:
    runner = JourneyYAMLRunner()
    result = runner.run(sample_journey_path)
    assert result.ok, f"{sample_journey_path.name} failed validation: {result.errors}"
    assert result.status == "validated"
    assert result.metrics.get("steps", 0) > 0


def test_missing_file_is_reported_cleanly(tmp_path: Path) -> None:
    result = JourneyYAMLRunner().run(tmp_path / "does-not-exist.yaml")
    assert not result.ok
    assert result.status == "missing"


def test_invalid_shape_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: incomplete\n")
    result = JourneyYAMLRunner().run(bad)
    assert not result.ok
    assert result.status == "invalid_shape"


@pytest.mark.e2e
def test_runner_bound_to_app_runs_to_completion(journey_runner, samples_dir: Path) -> None:
    result = journey_runner.run(samples_dir / "hello.yaml")
    assert result.status in {"completed", "failed", "cancelled"}
    assert result.journey_id is not None
    assert result.job_id is not None
