"""Unit tests for job archival candidate cut, step list, and S3 fallback filter."""

from __future__ import annotations

from nexus_ai_engine.services.archived_jobs_service import filter_archived_rows
from nexus_ai_engine.stages.job_archival import (
    JobArchivalStage,
    select_archive_candidates,
)


def _job(job_id: str, start: str, execution_number: int) -> dict:
    return {
        "PK": f"JOURNEY#JRN-{job_id}",
        "SK": f"JOB#{job_id}",
        "Data": {
            "jobId": job_id,
            "startTime": start,
            "executionNumber": execution_number,
        },
    }


def test_archival_stage_step_list() -> None:
    ids = [step["id"] for step in JobArchivalStage.STEP_DEFINITIONS]
    assert ids == [
        "count_jobs",
        "identify_candidates",
        "export_to_s3",
        "register_glue",
        "delete_from_dynamo",
    ]
    assert JobArchivalStage.STAGE_NAME == "Job Archival"


def test_candidate_selection_keeps_newest_globally() -> None:
    jobs = [
        _job("old-a", "2026-01-01T00:00:00Z", 1),
        _job("old-b", "2026-01-02T00:00:00Z", 2),
        _job("keep-1", "2026-03-01T00:00:00Z", 10),
        _job("keep-2", "2026-03-02T00:00:00Z", 11),
        _job("keep-3", "2026-03-03T00:00:00Z", 12),
    ]
    candidates = select_archive_candidates(jobs, keep=3, max_per_run=500)
    ids = {c["Data"]["jobId"] for c in candidates}
    assert ids == {"old-a", "old-b"}


def test_candidate_selection_respects_max_per_run() -> None:
    jobs = [_job(f"j{i}", f"2026-01-{i:02d}T00:00:00Z", i) for i in range(1, 11)]
    candidates = select_archive_candidates(jobs, keep=2, max_per_run=3)
    assert len(candidates) == 3
    kept = {c["Data"]["jobId"] for c in select_archive_candidates(jobs, keep=2, max_per_run=500)}
    assert "j10" not in kept
    assert "j9" not in kept


def test_candidate_selection_empty_when_under_keep() -> None:
    jobs = [_job("a", "2026-01-01T00:00:00Z", 1)]
    assert select_archive_candidates(jobs, keep=1000, max_per_run=500) == []


def test_s3_fallback_filter_by_job_id_and_date() -> None:
    rows = [
        {
            "job_id": "JOB-AAA",
            "execution_number": 10,
            "start_time": "2026-04-01T10:00:00Z",
            "status": "completed",
        },
        {
            "job_id": "JOB-BBB",
            "execution_number": 11,
            "start_time": "2026-04-10T10:00:00Z",
            "status": "failed",
        },
        {
            "job_id": "JOB-CCC",
            "execution_number": 12,
            "start_time": "2026-05-01T10:00:00Z",
            "status": "completed",
        },
    ]
    by_id = filter_archived_rows(rows, query="JOB-BBB", limit=50)
    assert [r["job_id"] for r in by_id] == ["JOB-BBB"]

    by_num = filter_archived_rows(rows, query="12", limit=50)
    assert [r["job_id"] for r in by_num] == ["JOB-CCC"]

    by_date = filter_archived_rows(rows, date_from="2026-04-05", date_to="2026-04-30", limit=50)
    assert [r["job_id"] for r in by_date] == ["JOB-BBB"]
