"""Deterministic step tool implementations."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from nexus_ai_engine.events import emit
from nexus_ai_engine.execution.in_memory_engine import (
    InMemoryEngine,
    StepFailure,
    StepTool,
)
from nexus_ai_engine.models import Job, LogEntry, ReportCreate, Step, StepResult


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _log(engine: InMemoryEngine, job: Job, step: StepResult, message: str, level: str = "INFO") -> None:
    engine._append_log(
        job.id,
        LogEntry(timestamp=_now(), level=level, step_id=step.step_id, message=message),
    )


async def _progress(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    pct: int,
    message: str,
) -> None:
    step.progress = max(0, min(100, pct))
    await engine.sse.broadcast(
        emit("task_progress", job.id, step.step_id, progress=step.progress, message=message)
    )


# ── Tool implementations ─────────────────────────────────────────────────


async def tool_noop(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Return immediately. Baseline for concurrency tests."""
    _log(engine, job, step, "noop: ok")


async def tool_sleep(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Sleep for `input.seconds` (default 0.05s).

    Sleep is chunked into 20 slices so cancellation is cooperative and
    progress updates are emitted during long sleeps. For reliable
    endurance tests keep seconds <= 2.
    """
    seconds = float((step_def.input or {}).get("seconds", 0.05))
    slices = max(1, min(20, int(seconds * 20) or 1))
    slice_dur = seconds / slices
    for i in range(1, slices + 1):
        if engine.is_cancelled(job.id):
            return
        await asyncio.sleep(slice_dur)
        await _progress(engine, job, step, int(i / slices * 100), f"slept {i}/{slices}")
    _log(engine, job, step, f"sleep: {seconds:.3f}s ok")


async def tool_count_to(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Emit `input.n` log lines at `input.delay_seconds` each.

    Used for log-volume, log-ordering, and log-search assertions.
    """
    n = int((step_def.input or {}).get("n", 10))
    delay = float((step_def.input or {}).get("delay_seconds", 0.0))
    level = str((step_def.input or {}).get("level", "INFO")).upper()
    for i in range(1, n + 1):
        if engine.is_cancelled(job.id):
            return
        _log(engine, job, step, f"count {i}/{n}", level=level)
        if delay:
            await asyncio.sleep(delay)
        await _progress(engine, job, step, int(i / n * 100), f"count {i}/{n}")
    ctx[f"{step.step_id}.count"] = n


async def tool_fail_after(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Emit `input.n_ticks` logs then raise StepFailure(`input.message`).

    Used to verify failure propagation, error_message population, and
    that later steps never run.
    """
    n_ticks = int((step_def.input or {}).get("n_ticks", 3))
    message = str((step_def.input or {}).get("message", "deterministic failure"))
    for i in range(1, n_ticks + 1):
        if engine.is_cancelled(job.id):
            return
        _log(engine, job, step, f"tick {i}/{n_ticks}")
        await _progress(engine, job, step, int(i / (n_ticks + 1) * 100), f"tick {i}")
    raise StepFailure(message)


async def tool_flaky(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Pseudo-random pass/fail seeded by `input.seed` + step_id.

    Retry semantics: every retry (job.trigger_reason starts with "retry")
    succeeds unconditionally, regardless of `success_rate`. That models
    "transient failure cleared after retry" cleanly, and — since each
    retry_job invocation spawns a fresh job with its own ctx — it does
    not require cross-job state.

    First-attempt behavior is deterministic: `seed` + `step_id` + the
    stage_id derived from `step_def.tool` (stable across the same job
    definition) seed the PRNG; if the roll > `success_rate`, the step
    fails.
    """
    seed = int((step_def.input or {}).get("seed", 0))
    success_rate = float((step_def.input or {}).get("success_rate", 0.5))

    if job.trigger_reason.startswith("retry"):
        _log(engine, job, step, "flaky: retry attempt, passing")
        return

    # Seed must be int/float/str/bytes/bytearray; combine into a stable string.
    seed_key = f"{seed}|{step.step_id}|{step_def.tool or ''}"
    rng = random.Random(seed_key)
    roll = rng.random()
    if roll > success_rate:
        raise StepFailure(f"flaky roll {roll:.3f} > threshold {success_rate:.3f}")
    _log(engine, job, step, f"flaky: rolled {roll:.3f} <= {success_rate:.3f}, passing")


async def tool_transform(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Apply a named transformation to the prior step's output.

    - `input.from_key` reads from ctx (default: literal `input.source`)
    - `input.fn` selects the transform: identity, upper, double, reverse, count
    - `input.to_key` writes the result back into ctx (default: <step_id>.out)

    Used for data-flow tests where each step consumes the previous
    step's output.
    """
    spec = step_def.input or {}
    from_key = spec.get("from_key")
    src_value: Any
    if from_key:
        if from_key not in ctx:
            raise StepFailure(f"transform: missing ctx key {from_key!r}")
        src_value = ctx[from_key]
    else:
        src_value = spec.get("source")

    fn = spec.get("fn", "identity")
    if fn == "identity":
        result = src_value
    elif fn == "upper":
        if not isinstance(src_value, str):
            raise StepFailure(f"transform upper: not a string: {type(src_value).__name__}")
        result = src_value.upper()
    elif fn == "double":
        if not isinstance(src_value, (int, float, list)):
            raise StepFailure(f"transform double: unsupported type {type(src_value).__name__}")
        result = src_value * 2
    elif fn == "reverse":
        if not isinstance(src_value, (str, list, tuple)):
            raise StepFailure(f"transform reverse: unsupported type {type(src_value).__name__}")
        result = src_value[::-1]
    elif fn == "count":
        try:
            result = len(src_value)
        except TypeError as exc:
            raise StepFailure(f"transform count: {exc}") from exc
    else:
        raise StepFailure(f"transform: unknown fn {fn!r}")

    to_key = spec.get("to_key", f"{step.step_id}.out")
    ctx[to_key] = result
    _log(engine, job, step, f"transform[{fn}]: {from_key or 'source'} -> {to_key}")


async def tool_gather(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Merge outputs of several prior steps into a single ctx key.

    `input.from_keys` = list of ctx keys to read.
    `input.to_key`    = where to write the merged list.

    Used to exercise fan-in pipelines.
    """
    spec = step_def.input or {}
    keys = spec.get("from_keys", [])
    if not isinstance(keys, list) or not keys:
        raise StepFailure("gather: input.from_keys must be a non-empty list")
    missing = [k for k in keys if k not in ctx]
    if missing:
        raise StepFailure(f"gather: missing ctx keys: {missing}")
    merged = [ctx[k] for k in keys]
    to_key = spec.get("to_key", f"{step.step_id}.out")
    ctx[to_key] = merged
    _log(engine, job, step, f"gather: {len(keys)} keys -> {to_key}")


async def tool_cancel_checkpoint(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Sleep in short slices, checking cancellation each slice.

    `input.total_seconds` = upper bound on run time.
    `input.check_every_seconds` = slice length.

    Used to exercise mid-step cooperative cancellation: if the job is
    cancelled mid-run the tool returns without raising, and the
    dispatcher sees the cancel flag and terminates the job cleanly.
    """
    total = float((step_def.input or {}).get("total_seconds", 5.0))
    every = float((step_def.input or {}).get("check_every_seconds", 0.05))
    elapsed = 0.0
    tick = 0
    while elapsed < total:
        if engine.is_cancelled(job.id):
            _log(engine, job, step, f"cancel_checkpoint: cancelled at {elapsed:.3f}s")
            return
        await asyncio.sleep(min(every, total - elapsed))
        elapsed += every
        tick += 1
        await _progress(
            engine, job, step, int(elapsed / total * 100), f"checkpoint {tick}"
        )
    _log(engine, job, step, f"cancel_checkpoint: completed {total:.3f}s")


async def tool_emit_report(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Create a Report artifact bound to this job/step.

    `input.title`   = report title (required)
    `input.summary` = optional text summary
    `input.data`    = optional dict payload

    Used by report-pipeline assertions.
    """
    spec = step_def.input or {}
    title = spec.get("title")
    if not title:
        raise StepFailure("emit_report: input.title required")
    await engine.create_job_report(
        job.journey_id,
        job.id,
        ReportCreate(
            step_id=step.step_id,
            title=title,
            summary=spec.get("summary"),
            data=spec.get("data") or {},
        ),
    )
    _log(engine, job, step, f"emit_report: {title!r}")


async def tool_cpu_spin(
    engine: InMemoryEngine,
    job: Job,
    step: StepResult,
    step_def: Step,
    ctx: dict[str, Any],
) -> None:
    """Busy-loop for `input.ms` milliseconds in a thread executor.

    Intended for event-loop-fairness tests: if implemented in the main
    thread, a long spin would freeze other jobs. The executor offload
    proves the engine can keep other jobs progressing during CPU-bound
    steps.
    """
    ms = int((step_def.input or {}).get("ms", 10))
    loop = asyncio.get_event_loop()

    def _spin() -> None:
        end = time.perf_counter() + (ms / 1000.0)
        # Pure CPU loop (no I/O), off the event loop.
        while time.perf_counter() < end:
            pass

    await loop.run_in_executor(None, _spin)
    _log(engine, job, step, f"cpu_spin: {ms}ms done")


# ── Registration helper ──────────────────────────────────────────────────


ALL_TOOLS: dict[str, StepTool] = {
    "noop": tool_noop,
    "sleep": tool_sleep,
    "count_to": tool_count_to,
    "fail_after": tool_fail_after,
    "flaky": tool_flaky,
    "transform": tool_transform,
    "gather": tool_gather,
    "cancel_checkpoint": tool_cancel_checkpoint,
    "emit_report": tool_emit_report,
    "cpu_spin": tool_cpu_spin,
}


def register_all(engine: InMemoryEngine) -> None:
    """Register every deterministic tool on the given engine.

    The caller is responsible for keeping the reference so tools remain
    registered for the engine's lifetime. Idempotent.
    """
    for name, tool in ALL_TOOLS.items():
        engine.register_step_tool(name, tool)
