"""In-memory engine backing the embedded journey UI.

Holds all journey/job/schedule/prompt/report state in per-process dicts.
Simulated job execution emits SSE events tick-by-tick so the UI's live
log drawer shows realistic progress without any real work being done.

This is the minimum we need to light up the reference server's routes so
the port-forward UI is useful today. The DynamoDB adapter can replace this
in phase 10 without changing the router contract.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Awaitable, Callable

from ..events import SimpleSSEManager as SSEManager, emit
from ..executor.manager import ExecutionManager
from ..journeys.service import DslJourneyStore
from ..models import (
    AggregateReport,
    Job,
    JobMetrics,
    JobRunRequest,
    JobStatus,
    Journey,
    JourneyCreate,
    JourneyStatus,
    JourneyUpdate,
    LogEntry,
    Prompt,
    PromptAuditEntry,
    PromptConfig,
    PromptUpdate,
    Report,
    ReportCreate,
    Schedule,
    ScheduleCreate,
    ScheduleUpdate,
    Stage,
    StageStatus,
    Step,
    StepResult,
)
from ..registry.registry import ToolRegistry

logger = logging.getLogger(__name__)


class StepFailure(Exception):
    """Raised by a deterministic step tool to mark the step as failed.

    The executor captures the message into `StepResult.error` and emits an
    ERROR log entry before moving the job to its failed terminal state.
    """


# Signature of a deterministic step tool. Imported by tests and the
# harness; not used by the shipped random simulation. The `is_cancelled`
# keyword is a no-arg callable returning True once the job has been
# marked for cancellation; tools that sleep for long periods should poll
# it periodically so cancellation is cooperative.
StepTool = Callable[
    ["InMemoryEngine", "Job", "StepResult", "Step", dict[str, Any]],
    Awaitable[None],
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


@dataclass
class InMemoryEngine:
    """Single source of truth for the embedded UI.

    Not thread-safe for multi-process; fine for a single-worker port-forward
    dev server. Every public method is async so routers can ``await`` them
    uniformly.
    """

    journeys: dict[str, Journey] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    jobs_by_journey: dict[str, list[str]] = field(default_factory=dict)
    job_logs: dict[str, list[LogEntry]] = field(default_factory=dict)
    schedules: dict[str, Schedule] = field(default_factory=dict)
    reports: dict[str, Report] = field(default_factory=dict)
    reports_by_job: dict[str, list[str]] = field(default_factory=dict)
    prompt_config: PromptConfig = field(default_factory=PromptConfig)
    _default_prompts: list[Prompt] = field(default_factory=list)
    _cancel_flags: set[str] = field(default_factory=set)
    _running_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    sse: SSEManager = field(default_factory=SSEManager)
    # Optional registry of deterministic step tools. When a Step has
    # `type="tool"` and a `tool` name that is registered here, the
    # executor dispatches to the tool instead of running the random
    # simulation. Production / UI-demo code leaves this empty, so the
    # 5 seeded journeys continue to use the lively random simulator.
    #
    # Each tool is an async callable:
    #     async def tool(engine, job, step, step_def, ctx, *, is_cancelled) -> None
    # The tool is expected to update `step.progress`, append logs via
    # `engine._append_log`, broadcast SSE events via `engine.sse.broadcast`,
    # raise StepFailure(msg) to fail the step, or return normally to
    # complete it. `ctx` is a shared dict passed between steps of the
    # same job so steps can read each other's outputs.
    step_tools: dict[str, StepTool] = field(default_factory=dict)
    dsl_store: DslJourneyStore = field(default_factory=DslJourneyStore)
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)
    execution_manager: ExecutionManager = field(default_factory=ExecutionManager)
    _execution_runtime: object | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.execution_manager.dispatcher.registry = self.tool_registry

    @property
    def execution_runtime(self):
        from ..execution.runtime_service import ExecutionRuntimeService

        if self._execution_runtime is None:
            self._execution_runtime = ExecutionRuntimeService(
                manager=self.execution_manager,
                sse=self.sse,
            )
        return self._execution_runtime

    def known_tool_ids(self) -> frozenset[str]:
        embedded = self.execution_manager.dispatcher.embedded.list_tools()
        return self.tool_registry.catalog_tool_ids() | frozenset(embedded)

    async def run_execution_to_completion(self, execution_id) -> None:
        """Background helper for POST /executions submit."""
        await self.execution_manager.run_to_completion(execution_id)

    async def list_journeys(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        capability: str | None = None,
        limit: int | None = None,
    ) -> list[Journey]:
        items = list(self.journeys.values())
        if query:
            q = query.lower()
            items = [j for j in items if q in j.name.lower() or q in j.id.lower()]
        if status:
            items = [j for j in items if j.status.value == status]
        if capability:
            items = [j for j in items if (j.capability or "") == capability]
        items.sort(key=lambda j: j.updated_at, reverse=True)
        if limit is not None:
            items = items[:limit]
        return items

    async def get_journey(self, journey_id: str) -> Journey | None:
        return self.journeys.get(journey_id)

    async def create_journey(self, data: JourneyCreate) -> Journey:
        now = _now()
        j = Journey(
            id=_new_id("JRN"),
            name=data.name,
            description=data.description,
            capability=data.capability,
            kind=data.kind,
            status=JourneyStatus.created,
            created_at=now,
            updated_at=now,
            stages=data.stages or [],
        )
        self.journeys[j.id] = j
        self.jobs_by_journey.setdefault(j.id, [])
        return j

    async def update_journey(self, journey_id: str, data: JourneyUpdate) -> Journey | None:
        j = self.journeys.get(journey_id)
        if not j:
            return None
        updated = j.model_copy(
            update={
                **{k: v for k, v in data.model_dump(exclude_unset=True).items()},
                "updated_at": _now(),
            }
        )
        self.journeys[journey_id] = updated
        return updated

    async def delete_journey(self, journey_id: str) -> bool:
        if journey_id not in self.journeys:
            return False
        # Cancel any running jobs for this journey
        for jid in list(self.jobs_by_journey.get(journey_id, [])):
            await self.cancel_job(journey_id, jid)
        self.journeys.pop(journey_id, None)
        self.jobs_by_journey.pop(journey_id, None)
        # Drop schedules pointing at this journey
        for sid, s in list(self.schedules.items()):
            if s.journey_id == journey_id:
                self.schedules.pop(sid, None)
        return True

    async def clone_journey(self, journey_id: str, new_name: str | None = None) -> Journey | None:
        src = self.journeys.get(journey_id)
        if not src:
            return None
        clone = src.model_copy(
            update={
                "id": _new_id("JRN"),
                "name": new_name or f"{src.name} (Copy)",
                "status": JourneyStatus.created,
                "created_at": _now(),
                "updated_at": _now(),
                "jobs_total": 0,
                "jobs_done": 0,
                "jobs_running": 0,
                "jobs_failed": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0,
            }
        )
        self.journeys[clone.id] = clone
        self.jobs_by_journey.setdefault(clone.id, [])
        return clone

    # ── Stages ──────────────────────────────────────────────────────────

    async def add_stage(self, journey_id: str, stage: Stage) -> Journey | None:
        j = self.journeys.get(journey_id)
        if not j:
            return None
        stages = list(j.stages) + [stage]
        updated = j.model_copy(update={"stages": stages, "updated_at": _now()})
        self.journeys[journey_id] = updated
        return updated

    async def update_stage(self, journey_id: str, stage_id: str, stage: Stage) -> Journey | None:
        j = self.journeys.get(journey_id)
        if not j:
            return None
        stages = [stage if s.id == stage_id else s for s in j.stages]
        updated = j.model_copy(update={"stages": stages, "updated_at": _now()})
        self.journeys[journey_id] = updated
        return updated

    async def delete_stage(self, journey_id: str, stage_id: str) -> Journey | None:
        j = self.journeys.get(journey_id)
        if not j:
            return None
        stages = [s for s in j.stages if s.id != stage_id]
        updated = j.model_copy(update={"stages": stages, "updated_at": _now()})
        self.journeys[journey_id] = updated
        return updated

    # ── Jobs ────────────────────────────────────────────────────────────

    async def list_jobs(self, journey_id: str, *, limit: int | None = 100) -> list[Job]:
        ids = list(reversed(self.jobs_by_journey.get(journey_id, [])))
        if limit is not None:
            ids = ids[:limit]
        return [self.jobs[jid] for jid in ids if jid in self.jobs]

    async def get_job(self, journey_id: str, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if not job or job.journey_id != journey_id:
            return None
        return job

    async def get_job_status(self, journey_id: str, job_id: str) -> dict | None:
        job = await self.get_job(journey_id, job_id)
        if not job:
            return None
        return {
            "jobId": job.id,
            "status": job.status.value,
            "progress": job.progress,
            "currentStepId": job.current_step_id,
            "durationSeconds": job.duration_seconds,
        }

    async def run_job(self, journey_id: str, req: JobRunRequest) -> Job | None:
        j = self.journeys.get(journey_id)
        if not j:
            return None
        stage = next((s for s in j.stages if s.id == req.stage_id), None)
        if not stage:
            return None

        execution_number = (
            max([self.jobs[jid].execution_number for jid in self.jobs_by_journey.get(journey_id, [])] or [0]) + 1
        )
        job = Job(
            id=_new_id("JOB"),
            journey_id=journey_id,
            stage_id=stage.id,
            stage_name=stage.name,
            execution_number=execution_number,
            status=JobStatus.running,
            progress=0,
            triggered_by=req.triggered_by,
            trigger_reason=req.reason or "manual",
            started_at=_now(),
            current_step_id=stage.steps[0].id if stage.steps else None,
            step_results=[
                StepResult(step_id=step.id, status=JobStatus.queued, progress=0) for step in stage.steps
            ],
        )
        self.jobs[job.id] = job
        self.jobs_by_journey.setdefault(journey_id, []).append(job.id)
        self.job_logs[job.id] = []

        # Update journey counters
        self._update_journey_counters(journey_id, delta_total=1, delta_running=1)

        # Kick off simulated execution
        task = asyncio.create_task(self._execute_simulated(job))
        self._running_tasks[job.id] = task
        return job

    async def cancel_job(self, journey_id: str, job_id: str) -> Job | None:
        job = await self.get_job(journey_id, job_id)
        if not job:
            return None
        if job.status not in (JobStatus.running, JobStatus.queued):
            return job
        self._cancel_flags.add(job_id)
        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        return self.jobs[job_id]

    async def retry_job(self, journey_id: str, job_id: str) -> Job | None:
        """Spawn a new job from the same stage."""
        old = await self.get_job(journey_id, job_id)
        if not old:
            return None
        return await self.run_job(
            journey_id, JobRunRequest(stage_id=old.stage_id, triggered_by="ui", reason=f"retry of {job_id}")
        )

    async def get_job_logs(self, journey_id: str, job_id: str) -> list[LogEntry]:
        job = await self.get_job(journey_id, job_id)
        if not job:
            return []
        return list(self.job_logs.get(job_id, []))

    async def search_job_logs(
        self, journey_id: str, job_id: str, query: str
    ) -> list[LogEntry]:
        entries = await self.get_job_logs(journey_id, job_id)
        q = query.lower()
        return [e for e in entries if q in e.message.lower()]

    async def get_job_errors(self, journey_id: str, job_id: str) -> list[LogEntry]:
        entries = await self.get_job_logs(journey_id, job_id)
        return [e for e in entries if e.level.upper() in ("ERROR", "CRITICAL")]

    async def stream_job(self, job_id: str) -> AsyncIterator[str]:
        async for chunk in self.sse.subscribe(job_id):
            yield chunk

    # ── Schedules ───────────────────────────────────────────────────────

    async def list_schedules(self, *, journey_id: str | None = None) -> list[Schedule]:
        items = list(self.schedules.values())
        if journey_id:
            items = [s for s in items if s.journey_id == journey_id]
        items.sort(key=lambda s: s.updated_at, reverse=True)
        return items

    async def get_schedule(self, schedule_id: str) -> Schedule | None:
        return self.schedules.get(schedule_id)

    async def create_schedule(self, data: ScheduleCreate) -> Schedule:
        now = _now()
        s = Schedule(
            id=_new_id("SCH"),
            journey_id=data.journey_id,
            stage_id=data.stage_id,
            interval_minutes=data.interval_minutes,
            enabled=data.enabled,
            created_at=now,
            updated_at=now,
            next_run_at=now + timedelta(minutes=data.interval_minutes) if data.enabled else None,
        )
        self.schedules[s.id] = s
        return s

    async def update_schedule(self, schedule_id: str, data: ScheduleUpdate) -> Schedule | None:
        s = self.schedules.get(schedule_id)
        if not s:
            return None
        changes = data.model_dump(exclude_unset=True)
        new_s = s.model_copy(update={**changes, "updated_at": _now()})
        if changes.get("enabled") is True and not new_s.next_run_at:
            new_s = new_s.model_copy(update={"next_run_at": _now() + timedelta(minutes=new_s.interval_minutes)})
        self.schedules[schedule_id] = new_s
        return new_s

    async def delete_schedule(self, schedule_id: str) -> bool:
        return self.schedules.pop(schedule_id, None) is not None

    async def run_schedule_now(self, schedule_id: str) -> Job | None:
        s = self.schedules.get(schedule_id)
        if not s:
            return None
        job = await self.run_job(s.journey_id, JobRunRequest(stage_id=s.stage_id, triggered_by="schedule", reason=f"schedule {schedule_id}"))
        if job:
            self.schedules[schedule_id] = s.model_copy(
                update={
                    "last_run_at": _now(),
                    "next_run_at": _now() + timedelta(minutes=s.interval_minutes) if s.enabled else None,
                    "last_status": "running",
                    "updated_at": _now(),
                }
            )
        return job

    # ── Prompts ─────────────────────────────────────────────────────────

    async def list_prompts(self) -> list[Prompt]:
        return list(self.prompt_config.prompts)

    async def get_prompt(self, prompt_id: str) -> Prompt | None:
        return next((p for p in self.prompt_config.prompts if p.id == prompt_id), None)

    async def list_prompt_types(self) -> list[str]:
        return sorted({p.type for p in self.prompt_config.prompts})

    async def update_prompt(self, prompt_id: str, data: PromptUpdate) -> Prompt | None:
        current = await self.get_prompt(prompt_id)
        if not current:
            return None
        updated = current.model_copy(
            update={
                "content": data.content,
                "version": current.version + 1,
                "updated_at": _now(),
                "is_default": False,
            }
        )
        self.prompt_config.prompts = [updated if p.id == prompt_id else p for p in self.prompt_config.prompts]
        self.prompt_config.audit.insert(
            0,
            PromptAuditEntry(
                timestamp=_now(),
                prompt_id=prompt_id,
                action="updated",
                note=data.note,
                previous_content=current.content,
            ),
        )
        return updated

    async def reset_prompts(self) -> list[Prompt]:
        self.prompt_config.prompts = [p.model_copy() for p in self._default_prompts]
        self.prompt_config.audit.insert(
            0,
            PromptAuditEntry(timestamp=_now(), prompt_id="*", action="reset", note="Reset to defaults"),
        )
        return list(self.prompt_config.prompts)

    async def prompt_audit_log(self, *, limit: int = 100) -> list[PromptAuditEntry]:
        return list(self.prompt_config.audit[:limit])

    # ── Reports ─────────────────────────────────────────────────────────

    async def list_job_reports(self, journey_id: str, job_id: str) -> list[Report]:
        ids = self.reports_by_job.get(job_id, [])
        return [self.reports[rid] for rid in ids if rid in self.reports]

    async def create_job_report(
        self, journey_id: str, job_id: str, data: ReportCreate
    ) -> Report | None:
        job = await self.get_job(journey_id, job_id)
        if not job:
            return None
        r = Report(
            id=_new_id("RPT"),
            journey_id=journey_id,
            job_id=job_id,
            step_id=data.step_id,
            title=data.title,
            summary=data.summary,
            data=data.data,
            created_at=_now(),
        )
        self.reports[r.id] = r
        self.reports_by_job.setdefault(job_id, []).append(r.id)
        return r

    async def aggregate_report(self, journey_id: str) -> AggregateReport | None:
        j = self.journeys.get(journey_id)
        if not j:
            return None
        jobs = await self.list_jobs(journey_id, limit=None)
        total = len(jobs)
        completed = sum(1 for x in jobs if x.status == JobStatus.completed)
        failed = sum(1 for x in jobs if x.status == JobStatus.failed)
        success_rate = (completed / total * 100.0) if total else 0.0
        durations = [x.duration_seconds for x in jobs if x.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        total_calls = sum(x.metrics.calls_processed for x in jobs)
        total_errors = sum(x.metrics.errors for x in jobs)
        top_errors: list[str] = []
        for job in jobs[:25]:
            if job.error_message:
                top_errors.append(job.error_message)
        return AggregateReport(
            journey_id=journey_id,
            generated_at=_now(),
            total_jobs=total,
            completed_jobs=completed,
            failed_jobs=failed,
            success_rate=success_rate,
            avg_duration_seconds=avg_duration,
            total_calls_processed=total_calls,
            total_errors=total_errors,
            top_error_messages=top_errors[:5],
            per_stage={
                s.id: {"name": s.name, "status": s.status.value}
                for s in j.stages
            },
        )

    # ── Deterministic step-tool registry ────────────────────────────────

    def register_step_tool(self, name: str, tool: StepTool) -> None:
        """Register a deterministic step tool.

        Tests and the harness use this to plug in step implementations
        that are invoked when a `Step` has `type="tool"` and `tool=<name>`.
        """
        self.step_tools[name] = tool

    def is_cancelled(self, job_id: str) -> bool:
        """Return True once `cancel_job` has been called for this job."""
        return job_id in self._cancel_flags

    # ── Helpers ─────────────────────────────────────────────────────────

    def _update_journey_counters(
        self,
        journey_id: str,
        *,
        delta_total: int = 0,
        delta_done: int = 0,
        delta_running: int = 0,
        delta_failed: int = 0,
    ) -> None:
        j = self.journeys.get(journey_id)
        if not j:
            return
        jobs_total = max(0, j.jobs_total + delta_total)
        jobs_done = max(0, j.jobs_done + delta_done)
        jobs_running = max(0, j.jobs_running + delta_running)
        jobs_failed = max(0, j.jobs_failed + delta_failed)
        success_rate = (jobs_done / jobs_total * 100.0) if jobs_total else 0.0
        durations = [
            self.jobs[jid].duration_seconds
            for jid in self.jobs_by_journey.get(journey_id, [])
            if jid in self.jobs and self.jobs[jid].duration_seconds
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        status = j.status
        if jobs_running > 0:
            status = JourneyStatus.running
        elif jobs_failed > 0 and jobs_done == 0:
            status = JourneyStatus.failed
        elif jobs_total > 0:
            status = JourneyStatus.completed if delta_running < 0 else j.status
        self.journeys[journey_id] = j.model_copy(
            update={
                "jobs_total": jobs_total,
                "jobs_done": jobs_done,
                "jobs_running": jobs_running,
                "jobs_failed": jobs_failed,
                "success_rate": success_rate,
                "avg_duration_seconds": avg_duration,
                "status": status,
                "updated_at": _now(),
            }
        )

    async def _execute_simulated(self, job: Job) -> None:
        """Execute each step of the stage.

        Hybrid strategy:
        - If a `Step` has `type="tool"` and `tool` matches a registered
          deterministic tool, dispatch to that tool. Tools own their own
          progress/logs/SSE emission and may raise `StepFailure` to fail.
        - Otherwise fall back to the original random-tick simulator so
          the shipped UI demo behaves exactly as before.

        Both paths share the same terminal-state bookkeeping below.
        """
        journey_id = job.journey_id
        started = job.started_at
        total_steps = len(job.step_results) or 1
        calls_processed = 0
        errors = 0
        completed_ok = True

        # Resolve the Stage.steps list so we can look up type/tool/input
        # for each StepResult. Falls back to an empty list if the journey
        # has been deleted mid-run.
        stage_steps: list[Step] = []
        src_journey = self.journeys.get(journey_id)
        if src_journey:
            src_stage = next(
                (s for s in src_journey.stages if s.id == job.stage_id), None
            )
            if src_stage:
                stage_steps = list(src_stage.steps)
        step_def_by_id: dict[str, Step] = {s.id: s for s in stage_steps}

        # Shared job-scope context passed between deterministic step tools.
        # The random simulator ignores it.
        ctx: dict[str, Any] = {}

        try:
            for idx, step in enumerate(job.step_results):
                if job.id in self._cancel_flags:
                    completed_ok = False
                    break

                step_def = step_def_by_id.get(step.step_id)
                tool_name = (
                    step_def.tool
                    if step_def is not None and step_def.type == "tool"
                    else None
                )
                tool = self.step_tools.get(tool_name) if tool_name else None

                # Step start (shared for both paths)
                job.current_step_id = step.step_id
                step.status = JobStatus.running
                step.started_at = _now()
                await self.sse.broadcast(
                    emit(
                        "step_status",
                        job.id,
                        step.step_id,
                        status="running",
                        progress=0,
                        step_index=idx,
                    )
                )
                await self._log_emit(
                    job, step.step_id, "INFO", f"Starting step {step.step_id}"
                )

                if tool is not None and step_def is not None:
                    # ── Deterministic tool path ─────────────────────────
                    try:
                        await tool(self, job, step, step_def, ctx)
                    except StepFailure as failure:
                        step.status = JobStatus.failed
                        step.ended_at = _now()
                        step.error = str(failure) or "Step failed"
                        errors += 1
                        await self._log_emit(
                            job,
                            step.step_id,
                            "ERROR",
                            f"Step {step.step_id} failed: {step.error}",
                        )
                        await self.sse.broadcast(
                            emit(
                                "step_status",
                                job.id,
                                step.step_id,
                                status="failed",
                                error=step.error,
                                step_index=idx,
                            )
                        )
                        completed_ok = False
                        break
                    if job.id in self._cancel_flags:
                        completed_ok = False
                        break
                    # Tool completed successfully; normalize step state.
                    step.status = JobStatus.completed
                    step.ended_at = _now()
                    step.progress = 100
                    # Advance whole-job progress proportionally.
                    job.progress = int(((idx + 1) / total_steps) * 100)
                    step.log_count = sum(
                        1 for e in self.job_logs.get(job.id, []) if e.step_id == step.step_id
                    )
                    await self.sse.broadcast(
                        emit(
                            "step_status",
                            job.id,
                            step.step_id,
                            status="completed",
                            progress=100,
                            step_index=idx,
                        )
                    )
                    await self._log_emit(
                        job, step.step_id, "INFO", f"Completed step {step.step_id}"
                    )
                    continue

                # ── Random-simulation fallback (existing UI-demo behavior) ──
                ticks = random.randint(4, 8)
                for tick in range(1, ticks + 1):
                    if job.id in self._cancel_flags:
                        completed_ok = False
                        break
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                    pct = int(tick / ticks * 100)
                    step.progress = pct
                    job.progress = int(((idx + (pct / 100.0)) / total_steps) * 100)
                    msg = _sample_log_line(step.step_id, tick)
                    calls_processed += random.randint(8, 25)
                    # Emit a clean task_progress (no message) and a separate
                    # log event. The legacy v1 UI also reads `message` off
                    # task_progress, so keep it for one release.
                    await self._log_emit(job, step.step_id, "INFO", msg)
                    await self.sse.broadcast(
                        emit(
                            "task_progress",
                            job.id,
                            step.step_id,
                            progress=pct,
                            current=tick,
                            total=ticks,
                            message=msg,
                        )
                    )

                if job.id in self._cancel_flags:
                    completed_ok = False
                    break

                # 5% random failure (skipped on retries to keep tests stable)
                if random.random() < 0.05 and not job.trigger_reason.startswith("retry"):
                    step.status = JobStatus.failed
                    step.ended_at = _now()
                    step.error = "Simulated transient failure"
                    errors += 1
                    await self._log_emit(
                        job,
                        step.step_id,
                        "ERROR",
                        f"Step {step.step_id} failed: simulated transient failure",
                    )
                    await self.sse.broadcast(
                        emit(
                            "step_status",
                            job.id,
                            step.step_id,
                            status="failed",
                            error=step.error,
                            step_index=idx,
                        )
                    )
                    completed_ok = False
                    break

                step.status = JobStatus.completed
                step.ended_at = _now()
                step.progress = 100
                await self.sse.broadcast(
                    emit(
                        "step_status",
                        job.id,
                        step.step_id,
                        status="completed",
                        progress=100,
                        step_index=idx,
                    )
                )
                await self._log_emit(
                    job, step.step_id, "INFO", f"Completed step {step.step_id}"
                )

            # Terminal state
            now = _now()
            if job.id in self._cancel_flags:
                job.status = JobStatus.cancelled
                self._cancel_flags.discard(job.id)
            elif completed_ok:
                job.status = JobStatus.completed
                job.progress = 100
            else:
                job.status = JobStatus.failed
                job.error_message = next(
                    (s.error for s in job.step_results if s.error), "Step failed"
                )

            job.ended_at = now
            job.duration_seconds = (now - started).total_seconds()
            job.metrics = JobMetrics(
                calls_processed=calls_processed,
                errors=errors,
                warnings=0,
                success_rate=100.0 if job.status == JobStatus.completed else max(
                    0.0, 100.0 * (1 - errors / max(total_steps, 1))
                ),
            )
            await self.sse.broadcast(
                emit(
                    "job_complete",
                    job.id,
                    status=job.status.value,
                    duration_seconds=job.duration_seconds,
                    metrics=job.metrics.model_dump(),
                )
            )
            await self.sse.close(job.id)

            # Update journey aggregates
            if job.status == JobStatus.completed:
                self._update_journey_counters(
                    journey_id, delta_done=1, delta_running=-1
                )
            elif job.status == JobStatus.failed:
                self._update_journey_counters(
                    journey_id, delta_failed=1, delta_running=-1
                )
            else:  # cancelled
                self._update_journey_counters(journey_id, delta_running=-1)
        except asyncio.CancelledError:
            job.status = JobStatus.cancelled
            job.ended_at = _now()
            job.duration_seconds = (job.ended_at - started).total_seconds()
            self._cancel_flags.discard(job.id)
            with suppress(Exception):
                await self.sse.broadcast(
                    emit("job_complete", job.id, status="cancelled")
                )
                await self.sse.close(job.id)
            self._update_journey_counters(journey_id, delta_running=-1)
        except Exception as exc:
            logger.exception("simulated execution crashed for job %s", job.id)
            job.status = JobStatus.failed
            job.error_message = str(exc)
            job.ended_at = _now()
            job.duration_seconds = (job.ended_at - started).total_seconds()
            with suppress(Exception):
                await self.sse.broadcast(emit("error", job.id, message=str(exc)))
                await self.sse.close(job.id)
            self._update_journey_counters(journey_id, delta_failed=1, delta_running=-1)
        finally:
            self._running_tasks.pop(job.id, None)

    def _append_log(self, job_id: str, entry: LogEntry) -> None:
        # Per-step grouping in the v2 UI and in the production prod UI both
        # require `step_id` on every log line. Reject silent gaps now so a
        # future stage that forgets to tag its logs fails loudly in tests
        # rather than producing an empty "Logs (0)" panel in the browser.
        if not entry.step_id:
            raise ValueError(
                "LogEntry.step_id is required; logs without a step cannot be "
                "grouped in the v2 UI"
            )
        self.job_logs.setdefault(job_id, []).append(entry)

    async def _log_emit(
        self, job: Job, step_id: str, level: str, message: str
    ) -> None:
        """Append a log entry AND broadcast a dedicated `log` SSE event.

        Pairs the persistent log buffer (`get_job_logs` / REST fallback) with
        the live stream so the v2 UI can render per-step lines in real time.
        Updates the matching `StepResult.log_count` so badge counters stay
        in sync without a per-tick recount over `self.job_logs`.
        """
        entry = LogEntry(timestamp=_now(), level=level, step_id=step_id, message=message)
        self._append_log(job.id, entry)
        for sr in job.step_results:
            if sr.step_id == step_id:
                sr.log_count += 1
                break
        await self.sse.broadcast(
            emit("log", job.id, step_id, level=level, message=message)
        )


_LOG_TEMPLATES = [
    "Processing batch {n}",
    "Reconciled {n} entities",
    "Validated rules on {n} records",
    "Normalized {n} rows",
    "Scored {n} candidates",
    "Matched {n} entries against reference",
    "Enriched {n} payloads",
    "Pushed {n} items downstream",
]


def _sample_log_line(step_id: str, tick: int) -> str:
    template = random.choice(_LOG_TEMPLATES)
    return f"[{step_id}] {template.format(n=random.randint(8, 128))} (tick {tick})"
