"""Live soak: enqueue all journeys repeatedly and watch the Redis queue."""

from __future__ import annotations

import pytest

from .soak_runner import BulkRunSoakRunner


@pytest.mark.heavy
@pytest.mark.live
@pytest.mark.asyncio
async def test_bulk_run_all_journeys_30min_soak(bulk_run_soak_runner: BulkRunSoakRunner) -> None:
    """Run bulk-run for every journey until ENDURANCE_DURATION_SECONDS (default 30m).

    Environment:
      ENDURANCE_BASE_URL — required (e.g. https://ai-engine.yourbrain.tech)
      ENDURANCE_DURATION_SECONDS — default 1800
      ENDURANCE_DRAIN_TIMEOUT_SECONDS — max wait per cycle for idle queue (default 1200)
      ENDURANCE_SUMMARY_MAX_SECONDS — fail if /queue/summary slower (default 5)
      ENDURANCE_JOBS_MAX_SECONDS — fail if /queue/jobs slower (default 15)
      ENDURANCE_MIN_JOURNEYS — default 55
      ENDURANCE_REPORT_PATH — JSON report path
    """
    report = await bulk_run_soak_runner.run()
    assert report.cycles_completed >= 1, "soak did not complete any bulk-run cycle"
    assert report.ok, report.summary_text()
