"""Seed the InMemoryEngine with demo journeys, jobs, schedules, prompts.

Populates the engine on startup so a first port-forward to the UI is
immediately useful. Five journeys modelled on nexus-backend's standard
stage set: order-to-cash, call-processing, demand-forecasting,
inventory-optimization, supply-chain-risk.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from ..models import (
    Job,
    JobMetrics,
    JobStatus,
    Journey,
    JourneyStatus,
    Prompt,
    PromptConfig,
    Schedule,
    Stage,
    StageStatus,
    Step,
    StepResult,
)
from .in_memory_engine import InMemoryEngine, _new_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _steps(*names_descs: tuple[str, str]) -> list[Step]:
    return [
        Step(id=f"step-{i+1}", name=name, description=desc, order=i + 1)
        for i, (name, desc) in enumerate(names_descs)
    ]


def _journey_templates() -> list[dict]:
    return [
        {
            "name": "Order-to-Cash Monitor",
            "description": "Entity resolution, three-way matching, anomaly detection, workflow actions, cash flow projection.",
            "capability": "order-to-cash",
            "kind": "order_to_cash",
            "stages": [
                Stage(
                    id="order_to_cash",
                    name="Order-to-Cash Monitor",
                    description="Match orders across Salesforce, SAP, Oracle and project cash flow.",
                    order=1,
                    status=StageStatus.completed,
                    steps=_steps(
                        ("Entity Resolution", "Match orders across Salesforce, SAP, Oracle"),
                        ("Three-Way Match", "Validate PO qty = delivered qty = invoiced qty"),
                        ("Anomaly Scoring", "Score each order for anomalies vs baselines"),
                        ("Risk Prioritization", "Rank orders by composite risk score"),
                        ("Cash Flow Projection", "Forecast incoming cash over the next 30 days"),
                    ),
                ),
            ],
        },
        {
            "name": "Call Processing Pipeline",
            "description": "Ingest, transcribe, classify, and index contact-center calls.",
            "capability": "call-processing",
            "kind": "call_processing",
            "stages": [
                Stage(
                    id="call_ingest",
                    name="Call Ingest",
                    description="Pull recordings from WXCC and stage them for processing.",
                    order=1,
                    status=StageStatus.completed,
                    steps=_steps(
                        ("Fetch Recordings", "Download call recordings from WXCC"),
                        ("Validate Media", "Check duration, bitrate, codec"),
                        ("Checkpoint", "Persist file references to metadata store"),
                    ),
                ),
                Stage(
                    id="call_process",
                    name="Call Processing",
                    description="Transcribe, classify, and score each call.",
                    order=2,
                    status=StageStatus.pending,
                    steps=_steps(
                        ("Transcription", "Run ASR and produce timestamped transcripts"),
                        ("Diarization", "Separate speakers and label turns"),
                        ("Classification", "Assign intent, sentiment, and topics"),
                        ("Quality Scoring", "Score compliance + quality against rubric"),
                    ),
                ),
            ],
        },
        {
            "name": "Demand Forecasting Engine",
            "description": "Feature engineering, base forecast, scenario overlays, error analysis.",
            "capability": "demand-forecasting",
            "kind": "demand_forecasting",
            "stages": [
                Stage(
                    id="demand_forecasting",
                    name="Demand Forecasting",
                    description="Forecast SKU-level demand across warehouses for the next 12 weeks.",
                    order=1,
                    status=StageStatus.completed,
                    steps=_steps(
                        ("Feature Build", "Assemble lag, seasonality, and promo features"),
                        ("Base Forecast", "Fit the baseline model per SKU/warehouse"),
                        ("Scenario Overlays", "Apply promo, weather, and holiday overlays"),
                        ("Error Analysis", "Compare to actuals and flag drift"),
                    ),
                ),
            ],
        },
        {
            "name": "Inventory Optimization",
            "description": "Stock-out risk, replenishment recommendations, safety stock tuning.",
            "capability": "inventory-optimization",
            "kind": "inventory_optimization",
            "stages": [
                Stage(
                    id="inventory_optimization",
                    name="Inventory Optimization",
                    description="Rank SKUs by stock-out risk and recommend replenishment.",
                    order=1,
                    status=StageStatus.pending,
                    steps=_steps(
                        ("Demand Signal Ingest", "Pull forecasts and recent sales"),
                        ("Lead-time Model", "Fit per-supplier lead-time distributions"),
                        ("Stock-out Risk", "Compute stock-out probability per SKU"),
                        ("Replenishment Plan", "Produce PO recommendations"),
                    ),
                ),
            ],
        },
        {
            "name": "Supply Chain Risk",
            "description": "Supplier concentration, geo risk, disruption scenarios.",
            "capability": "supply-chain-risk",
            "kind": "supply_chain_risk",
            "stages": [
                Stage(
                    id="supply_chain_risk",
                    name="Supply Chain Risk",
                    description="Identify high-risk suppliers and simulate disruption scenarios.",
                    order=1,
                    status=StageStatus.pending,
                    steps=_steps(
                        ("Supplier Graph", "Build upstream dependency graph"),
                        ("Concentration Risk", "Score concentration by geo and tier"),
                        ("Disruption Simulation", "Run tabletop disruption scenarios"),
                        ("Mitigation Plan", "Produce actionable mitigations"),
                    ),
                ),
            ],
        },
    ]


def _default_prompts() -> list[Prompt]:
    now = _now()
    return [
        Prompt(
            id="journey_planner",
            name="Journey Planner",
            description="Plans the sequence of stages required to achieve a goal.",
            type="system",
            content=(
                "You are a planner. Given the user goal, produce an ordered list of "
                "stages with clear step names and success criteria."
            ),
            version=1,
            updated_at=now,
            is_default=True,
        ),
        Prompt(
            id="stage_runner",
            name="Stage Runner",
            description="Executes a single stage, producing structured output.",
            type="system",
            content=(
                "You are a stage runner. Execute the steps of the given stage in order. "
                "Return a JSON object summarising the output of each step."
            ),
            version=1,
            updated_at=now,
            is_default=True,
        ),
        Prompt(
            id="anomaly_scorer",
            name="Anomaly Scorer",
            description="Scores records for anomalies against provided baselines.",
            type="system",
            content=(
                "Score each record in the input array against the supplied baseline. "
                "Return a parallel array of floats in [0,1]."
            ),
            version=1,
            updated_at=now,
            is_default=True,
        ),
        Prompt(
            id="call_classifier",
            name="Call Classifier",
            description="Assigns intent, sentiment, and topics to a call transcript.",
            type="system",
            content=(
                "Classify the given contact-center transcript. Return JSON with keys: "
                "intent, sentiment, topics (array of up to 5)."
            ),
            version=1,
            updated_at=now,
            is_default=True,
        ),
    ]


def _fake_historical_job(journey: Journey, stage: Stage, n: int, older_than_days: int) -> Job:
    started = _now() - timedelta(days=older_than_days, minutes=random.randint(0, 90))
    duration = random.uniform(6.0, 45.0)
    ended = started + timedelta(seconds=duration)
    status = random.choices(
        [JobStatus.completed, JobStatus.failed, JobStatus.cancelled],
        weights=[0.86, 0.10, 0.04],
        k=1,
    )[0]
    step_results = [
        StepResult(
            step_id=s.id,
            status=JobStatus.completed if status == JobStatus.completed else status,
            progress=100 if status != JobStatus.failed else random.randint(30, 95),
            started_at=started,
            ended_at=ended,
            log_count=random.randint(5, 25),
        )
        for s in stage.steps
    ]
    calls = random.randint(80, 900)
    errors = random.randint(0, 8) if status != JobStatus.completed else random.randint(0, 2)
    return Job(
        id=_new_id("JOB"),
        journey_id=journey.id,
        stage_id=stage.id,
        stage_name=stage.name,
        execution_number=n,
        status=status,
        progress=100 if status == JobStatus.completed else 0,
        triggered_by="schedule" if random.random() < 0.5 else "ui",
        trigger_reason="scheduled" if random.random() < 0.5 else "manual",
        started_at=started,
        ended_at=ended,
        duration_seconds=duration,
        current_step_id=stage.steps[-1].id if stage.steps else None,
        step_results=step_results,
        metrics=JobMetrics(
            calls_processed=calls,
            errors=errors,
            warnings=random.randint(0, 4),
            success_rate=100.0 if status == JobStatus.completed else random.uniform(40.0, 95.0),
        ),
        error_message="Simulated failure" if status == JobStatus.failed else None,
    )


def seed(engine: InMemoryEngine, *, seed_random: int | None = 42) -> None:
    """Populate the engine with demo data in place."""
    if seed_random is not None:
        random.seed(seed_random)

    # Journeys
    for idx, tpl in enumerate(_journey_templates()):
        now = _now() - timedelta(days=30 - idx * 5)
        journey = Journey(
            id=_new_id("JRN"),
            name=tpl["name"],
            description=tpl["description"],
            capability=tpl["capability"],
            kind=tpl["kind"],
            status=JourneyStatus.created,
            created_at=now,
            updated_at=now,
            stages=tpl["stages"],
        )
        engine.journeys[journey.id] = journey
        engine.jobs_by_journey.setdefault(journey.id, [])

        # Historical jobs (2-5 per stage)
        for stage in journey.stages:
            count = random.randint(2, 5)
            for n in range(1, count + 1):
                job = _fake_historical_job(journey, stage, n, older_than_days=random.randint(0, 12))
                engine.jobs[job.id] = job
                engine.jobs_by_journey[journey.id].append(job.id)
                # Also seed a short log trail
                engine.job_logs[job.id] = [
                    # Keep it tiny — historical jobs show a handful of lines
                    # when opened, the new runs build bigger logs live.
                ]

        # Recompute counters
        jobs = [engine.jobs[jid] for jid in engine.jobs_by_journey[journey.id]]
        total = len(jobs)
        done = sum(1 for x in jobs if x.status == JobStatus.completed)
        failed = sum(1 for x in jobs if x.status == JobStatus.failed)
        running = sum(1 for x in jobs if x.status == JobStatus.running)
        durations = [x.duration_seconds for x in jobs if x.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        success_rate = (done / total * 100.0) if total else 0.0
        engine.journeys[journey.id] = journey.model_copy(
            update={
                "jobs_total": total,
                "jobs_done": done,
                "jobs_failed": failed,
                "jobs_running": running,
                "avg_duration_seconds": avg_duration,
                "success_rate": success_rate,
                "status": (
                    JourneyStatus.failed if failed and not done
                    else JourneyStatus.completed if done and not running
                    else JourneyStatus.created
                ),
            }
        )

    # Schedules for the first 3 journeys
    journey_ids = list(engine.journeys.keys())
    for i, jid in enumerate(journey_ids[:3]):
        j = engine.journeys[jid]
        if not j.stages:
            continue
        stage = j.stages[0]
        s = Schedule(
            id=_new_id("SCH"),
            journey_id=jid,
            stage_id=stage.id,
            interval_minutes=15 * (i + 1),
            enabled=i != 2,  # last one disabled to show both states
            created_at=_now(),
            updated_at=_now(),
            last_run_at=_now() - timedelta(minutes=12),
            next_run_at=_now() + timedelta(minutes=15 * (i + 1)),
            last_status="completed",
        )
        engine.schedules[s.id] = s

    # Prompts
    prompts = _default_prompts()
    engine._default_prompts = [p.model_copy() for p in prompts]
    engine.prompt_config = PromptConfig(prompts=prompts, audit=[])
