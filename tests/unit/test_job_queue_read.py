"""Unit tests for queue snapshot helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from nexus_ai_engine.services import job_queue_service as q


def test_get_stage_jobs_queued_formula() -> None:
    with patch.object(q, "get_consumer_lag", return_value=3), patch.object(
        q, "get_pending_count", return_value=2
    ), patch.object(q, "get_active_job_count", return_value=1):
        assert q.get_stage_jobs_queued() == 4


def test_list_queue_jobs_all_merges() -> None:
    waiting = [{"stream_id": "1-0", "state": "waiting", "job_id": "a"}]
    pending = [{"stream_id": "2-0", "state": "running", "job_id": "b"}]
    with patch.object(q, "list_waiting_jobs", return_value=waiting), patch.object(
        q, "list_pending_jobs", return_value=pending
    ):
        rows = q.list_queue_jobs(state="all", limit=10)
        assert len(rows) == 2


def test_get_queue_snapshot_fields() -> None:
    with patch.object(q, "get_consumer_lag", return_value=1), patch.object(
        q, "get_pending_count", return_value=0
    ), patch.object(q, "get_active_job_count", return_value=0), patch.object(
        q, "get_max_global_jobs", return_value=10
    ), patch.object(
        q, "get_consumer_count", return_value=1
    ):
        snap = q.get_queue_snapshot()
        assert snap["lag"] == 1
        assert snap["max_global"] == 10
        assert "generated_at" in snap
