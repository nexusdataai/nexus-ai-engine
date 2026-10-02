"""Unit tests for queue snapshot helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from nexus_ai_engine.services import job_queue_service as q


def test_get_stage_jobs_queued_formula() -> None:
    with patch.object(q, "get_waiting_count", return_value=4):
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
    with patch.object(q, "get_waiting_count", return_value=1), patch.object(
        q, "get_pending_count", return_value=0
    ), patch.object(q, "get_active_job_count", return_value=0), patch.object(
        q, "get_max_global_jobs", return_value=10
    ), patch.object(
        q, "get_consumer_count", return_value=1
    ), patch.object(
        q, "get_live_consumer_count", return_value=1
    ), patch.object(
        q, "get_worker_threads", return_value=3
    ):
        snap = q.get_queue_snapshot()
        assert snap["lag"] == 1
        assert snap["max_global"] == 10
        assert snap["worker_threads"] == 3
        assert snap["running_capacity"] == 3
        assert "generated_at" in snap


def test_get_running_capacity_caps_at_global() -> None:
    with patch.object(q, "get_max_global_jobs", return_value=5), patch.object(
        q, "get_live_consumer_count", return_value=3
    ), patch.object(q, "get_worker_threads", return_value=3):
        assert q.get_running_capacity() == 5


def test_reclaim_stale_jobs_limit_zero() -> None:
    assert q.reclaim_stale_jobs("c1", limit=0) == []


def test_consumer_health_busy_worker_is_healthy() -> None:
    assert q.consumer_health(idle_ms=180_000, pending_count=1) == "healthy"
    assert q.consumer_health(idle_ms=5_000, pending_count=1) == "healthy"


def test_consumer_health_idle_and_stale() -> None:
    assert q.consumer_health(idle_ms=5_000, pending_count=0) == "healthy"
    assert q.consumer_health(idle_ms=180_000, pending_count=0) == "stale"


def test_list_waiting_jobs_without_redis7_lag() -> None:
    job_fields = {
        "job_id": "JOB-1",
        "journey_id": "JRN-1",
        "job_kind": "transformation",
        "stage_id": "",
        "stage_ids": "[]",
        "triggered_by": "ui",
        "reason": "",
        "job_config": "{}",
        "enqueued_at": "100",
    }
    fake_client = MagicMock()
    fake_client.xrange.return_value = [("2-0", job_fields)]
    with (
        patch.object(q, "_group_info", return_value={"last-delivered-id": "1-0"}),
        patch.object(q, "list_pending_jobs", return_value=[]),
        patch.object(q, "_client", return_value=fake_client),
    ):
        rows = q.list_waiting_jobs(limit=50)
    assert len(rows) == 1
    assert rows[0]["job_id"] == "JOB-1"
    assert rows[0]["state"] == "waiting"


def test_list_waiting_jobs_from_waiting_set() -> None:
    job_fields = {
        "job_id": "JOB-WAIT",
        "journey_id": "JRN-1",
        "job_kind": "transformation",
        "stage_id": "",
        "stage_ids": "[]",
        "triggered_by": "ui",
        "reason": "",
        "job_config": "{}",
        "enqueued_at": "100",
    }
    fake_client = MagicMock()
    fake_client.smembers.return_value = {"9-0"}
    fake_client.xrange.return_value = [("9-0", job_fields)]
    with (
        patch.object(q, "list_pending_jobs", return_value=[]),
        patch.object(q, "_client", return_value=fake_client),
    ):
        rows = q.list_waiting_jobs(limit=50)
    assert len(rows) == 1
    assert rows[0]["job_id"] == "JOB-WAIT"
    assert rows[0]["state"] == "waiting"


def test_enqueue_jobs_writes_waiting_set() -> None:
    pipe = MagicMock()
    pipe.execute.return_value = ["10-0", "11-0"]
    fake = MagicMock()
    fake.pipeline.return_value = pipe
    with patch.object(q, "ensure_consumer_group"), patch.object(q, "_client", return_value=fake):
        ids = q.enqueue_jobs(
            [
                {"job_id": "JOB-A", "journey_id": "JRN-1"},
                {"job_id": "JOB-B", "journey_id": "JRN-2"},
            ]
        )
    assert ids == ["10-0", "11-0"]
    assert pipe.xadd.call_count == 2
    fake.sadd.assert_called_once()


def test_get_consumer_lag_falls_back_without_lag_field() -> None:
    fake_client = MagicMock()
    fake_client.xinfo_groups.return_value = [
        {"name": "ai-engine-workers", "last-delivered-id": "1-0"}
    ]
    fake_client.xrange.return_value = [("2-0", {}), ("3-0", {})]
    with patch.object(q, "_client", return_value=fake_client):
        assert q.get_consumer_lag() == 2
