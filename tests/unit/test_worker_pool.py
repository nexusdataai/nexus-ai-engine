"""Unit tests for threaded job-worker slotting and DSL isolation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from nexus_ai_engine.execution.transformation_job_executor import TransformationJobExecutor
from nexus_ai_engine.services.job_queue_service import QueuedJob
from nexus_ai_engine.workers import job_worker as jw


def _future(done: bool) -> MagicMock:
    fut = MagicMock()
    fut.done.return_value = done
    fut.exception.return_value = None
    return fut


def test_slots_free_when_pool_full() -> None:
    in_flight = {_future(False), _future(False), _future(False)}
    assert jw.slots_free(in_flight, 3) == 0
    assert len(in_flight) == 3


def test_slots_free_prunes_finished() -> None:
    done = _future(True)
    pending = _future(False)
    in_flight = {done, pending}
    assert jw.slots_free(in_flight, 3) == 2
    assert done not in in_flight
    assert pending in in_flight


def test_reclaim_for_slots_skips_when_full() -> None:
    with patch.object(jw, "reclaim_stale_jobs") as reclaim:
        assert jw.reclaim_for_slots("c1", 0) == []
        reclaim.assert_not_called()


def test_reclaim_for_slots_caps_limit() -> None:
    jobs = [QueuedJob(stream_id="1-0", job_id="JOB-1", journey_id="JRN-1")]
    with patch.object(jw, "reclaim_stale_jobs", return_value=jobs) as reclaim:
        got = jw.reclaim_for_slots("c1", 2)
    assert got == jobs
    reclaim.assert_called_once_with("c1", limit=2)


def test_cancel_lock_roundtrip() -> None:
    job_id = f"JOB-LOCK-{uuid4().hex[:8]}"
    TransformationJobExecutor.cancel_job_execution(job_id)
    assert TransformationJobExecutor.is_job_cancelled(job_id) is True
    TransformationJobExecutor.clear_cancelled_job(job_id)
    with patch(
        "nexus_ai_engine.services.job_queue_service.is_queue_mode",
        return_value=False,
    ):
        assert TransformationJobExecutor.is_job_cancelled(job_id) is False


def test_run_dsl_creates_runtime_per_job() -> None:
    runtime = MagicMock()
    runtime.run_to_completion = AsyncMock()
    job = QueuedJob(
        stream_id="1-0",
        job_id=str(uuid4()),
        journey_id="JRN-1",
        job_kind="dsl_execution",
    )
    with patch.object(jw, "_new_runtime_service", return_value=runtime) as factory:
        jw._run_dsl_job(job)
        jw._run_dsl_job(job)
    assert factory.call_count == 2
