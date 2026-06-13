"""Unit tests for the Phase 0 backbone changes:

- ``InMemoryEngine._append_log`` rejects ``LogEntry`` without ``step_id``.
- ``InMemoryEngine._log_emit`` updates ``StepResult.log_count``.
- ``events.sse._format_sse`` emits the dual-frame format (named + default)
  whenever the payload carries a ``type``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from nexus_ai_engine.events.sse import _format_sse
from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import (
    Job,
    JobStatus,
    LogEntry,
    StepResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_append_log_requires_step_id() -> None:
    engine = InMemoryEngine()
    with pytest.raises(ValueError, match="step_id"):
        engine._append_log(
            "JOB-X",
            LogEntry(timestamp=_now(), level="INFO", message="missing step"),
        )


def test_append_log_accepts_step_id() -> None:
    engine = InMemoryEngine()
    engine._append_log(
        "JOB-X",
        LogEntry(timestamp=_now(), level="INFO", step_id="step-1", message="ok"),
    )
    assert len(engine.job_logs["JOB-X"]) == 1


async def test_log_emit_updates_step_log_count() -> None:
    engine = InMemoryEngine()
    job = Job(
        id="JOB-1",
        journey_id="JRN-1",
        stage_id="stg",
        stage_name="S",
        execution_number=1,
        status=JobStatus.running,
        started_at=_now(),
        step_results=[
            StepResult(step_id="step-1", status=JobStatus.running),
            StepResult(step_id="step-2", status=JobStatus.queued),
        ],
    )

    await engine._log_emit(job, "step-1", "INFO", "first")
    await engine._log_emit(job, "step-1", "WARN", "second")
    await engine._log_emit(job, "step-2", "INFO", "other")

    counts = {sr.step_id: sr.log_count for sr in job.step_results}
    assert counts == {"step-1": 2, "step-2": 1}
    # Logs are also persisted in the job log buffer for REST fallback.
    assert len(engine.job_logs["JOB-1"]) == 3


def test_format_sse_emits_dual_frame_when_typed() -> None:
    payload = {"type": "log", "job_id": "J1", "step_id": "s1",
               "data": {"level": "INFO", "message": "hi"},
               "timestamp": "2025-01-01T00:00:00Z"}
    out = _format_sse(payload)

    # Named-event frame first, default-channel frame second; both terminated
    # by a blank line so EventSource parses them as separate events.
    assert out.startswith("event: log\ndata: ")
    assert "\n\ndata: " in out  # the second (default) frame
    assert out.endswith("\n\n")
    assert out.count("data: ") == 2

    # Both frames carry an identical JSON body.
    chunks = [c for c in out.split("\n\n") if c.strip()]
    bodies = []
    for c in chunks:
        for line in c.splitlines():
            if line.startswith("data: "):
                bodies.append(json.loads(line[len("data: "):]))
    assert len(bodies) == 2
    assert bodies[0] == bodies[1] == payload


def test_format_sse_falls_back_to_default_only_for_untyped() -> None:
    payload = {"job_id": "J1", "hello": "world"}
    out = _format_sse(payload)
    assert "event: " not in out
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    assert out.count("data: ") == 1
