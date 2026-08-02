"""Demo stage implementations shipped with the library.

Provides 7 ``BaseStage`` subclasses covering the same 5 demo journeys the
in-memory engine seeds (Order-to-Cash, Call Processing — three stages,
Demand Forecasting, Inventory Optimization, Supply Chain Risk). Each step
performs synthetic work — a bounded random sleep plus a realistic-looking
log line per "tick" — so the production engine can be exercised
end-to-end (DynamoDB live-log writes, S3 uploads, SSE event fan-out)
without a host application registering domain stages.

Use cases:

- Performance / load testing of the engine framework itself
  (``TransformationJobExecutor``, SSE manager, DynamoDB I/O, S3 uploads)
  without confounding it with real algorithm complexity.
- Smoke testing a fresh standalone deploy (``nexus-ai-engine serve``)
  before the host wires real stages.
- Visual sandbox for the v2 UI's GitHub-Actions-style stepper, log
  console, and live SSE event flow against a real production Engine.

The same ``DEMO_JOURNEYS`` constant feeds both the stage registration
helper and ``scripts/seed-sample-journeys.sh``, so the journey shapes the
seed script POSTs always match the runnable stage step lists.

Registration is opt-in. ``factory.build_engine()`` does NOT register
these by default — embedding hosts (e.g. ``nexus-backend``) would not
want their ``order_to_cash`` shadowed by a synthetic stage. The
standalone CLI flips them on with the ``--register-demo-stages`` flag,
which is on by default for ``serve`` so the pod is usable out of the box.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Type

from .base_stage import BaseStage
from .registry import register_stage


# ── Canonical demo journey + stage + step definitions ──────────────────
# Single source of truth: consumed by `register_demo_stages` to build
# stage classes AND by `scripts/seed-sample-journeys.sh` (via the
# ``--print-demo-journeys`` CLI command) to POST matching journeys.
#
# Step shape (each dict):
#   id            unique within its stage; appears in SSE step_id field.
#   name          human-readable label rendered in the v2 stepper.
#   description   tooltip/subtitle shown under the step name.
#   ticks         optional fixed tick count (otherwise random 4-8).
#   sleep_min     optional lower bound on per-tick sleep, default 0.1s.
#   sleep_max     optional upper bound on per-tick sleep, default 0.4s.
#   fail          if True, the step raises after its ticks complete.
#                 Used for failure-path stress testing; default False.
#   fail_reason   optional human-readable error message when fail=True.
DEMO_JOURNEYS: List[Dict[str, Any]] = [
    {
        "name": "Order-to-Cash Monitor",
        "description": "Reconcile orders across CRM/ERP/billing, score anomalies, project cash flow.",
        "odaComponentType": "order-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "order_to_cash",
                "name": "Order-to-Cash",
                "description": "Match orders across Salesforce, SAP, Oracle and project cash flow.",
                "steps": [
                    {"id": "entity_resolution", "name": "Entity Resolution",
                     "description": "Match orders across Salesforce, SAP, Oracle"},
                    {"id": "three_way_match", "name": "Three-Way Match",
                     "description": "Validate PO qty = delivered qty = invoiced qty"},
                    {"id": "anomaly_scoring", "name": "Anomaly Scoring",
                     "description": "Score each order vs baseline patterns"},
                    {"id": "risk_priority", "name": "Risk Prioritization",
                     "description": "Rank orders by composite risk score"},
                    {"id": "cash_projection", "name": "Cash Flow Projection",
                     "description": "Forecast incoming cash over 30 days"},
                ],
            },
        ],
    },
    {
        "name": "Call Processing Pipeline",
        "description": "Ingest, transcribe, classify, and index contact-center call recordings.",
        "odaComponentType": "service-management",
        "priority": "medium",
        "stages": [
            {
                "stage_id": "call_ingest", "name": "Call Ingest",
                "description": "Pull recordings and validate media before processing.",
                "steps": [
                    {"id": "fetch", "name": "Fetch Recordings",
                     "description": "Pull recordings from WXCC"},
                    {"id": "validate", "name": "Validate Media",
                     "description": "Check duration, bitrate, codec"},
                ],
            },
            {
                "stage_id": "transcribe", "name": "Transcribe",
                "description": "Speech-to-text + speaker diarization.",
                "steps": [
                    {"id": "stt", "name": "Speech-to-Text",
                     "description": "Whisper-1 transcription"},
                    {"id": "diarize", "name": "Speaker Diarization",
                     "description": "Identify agent vs customer turns"},
                ],
            },
            {
                "stage_id": "analyze", "name": "Analyze",
                "description": "Intent classification + sentiment scoring.",
                "steps": [
                    {"id": "intent", "name": "Intent Classification",
                     "description": "Map utterances to intent taxonomy"},
                    {"id": "sentiment", "name": "Sentiment Scoring",
                     "description": "Per-turn sentiment delta"},
                ],
            },
        ],
    },
    {
        "name": "Demand Forecasting Engine",
        "description": "8-week SKU x region demand forecast with promotion lift and cannibalization adjustments.",
        "odaComponentType": "inventory-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "demand_forecast", "name": "Demand Forecast",
                "description": "Per-SKU per-region 8-week forecast pipeline.",
                "steps": [
                    {"id": "feature_eng", "name": "Feature Engineering",
                     "description": "Aggregate 9 entities into SKU x region matrix"},
                    {"id": "model_ensemble", "name": "Model Ensemble",
                     "description": "Generate base forecasts (ETS / Prophet / XGBoost)"},
                    {"id": "promo_adjust", "name": "Promotion Adjustments",
                     "description": "Apply lift factors per promo type"},
                    {"id": "cannib_adjust", "name": "Cannibalization",
                     "description": "Discount substituted-SKU demand"},
                    {"id": "consensus", "name": "Consensus Forecast",
                     "description": "Reconcile ensemble + adjustments"},
                    {"id": "alerts", "name": "Alert Generation",
                     "description": "Flag forecasts > 25% deviation"},
                ],
            },
        ],
    },
    {
        "name": "Inventory Optimization",
        "description": "Compute reorder points, safety stock, EOQ across 5 DCs.",
        "odaComponentType": "inventory-management",
        "priority": "medium",
        "stages": [
            {
                "stage_id": "inventory_opt", "name": "Inventory Optimization",
                "description": "Per-SKU per-DC inventory parameter optimisation.",
                "steps": [
                    {"id": "abc_classify", "name": "ABC Classification",
                     "description": "Pareto-rank SKUs by revenue contribution"},
                    {"id": "lead_time", "name": "Lead-Time Analysis",
                     "description": "Compute supplier lead-time distributions"},
                    {"id": "safety_stock", "name": "Safety Stock",
                     "description": "Set per-SKU safety stock at 95% service level"},
                    {"id": "reorder_point", "name": "Reorder Point",
                     "description": "ROP = avg-daily-demand * lead-time + SS"},
                ],
            },
        ],
    },
    {
        "name": "Supply Chain Risk",
        "description": "Identify high-risk suppliers and simulate disruption scenarios.",
        "odaComponentType": "resource-management",
        "priority": "critical",
        "stages": [
            {
                "stage_id": "supply_risk", "name": "Supply Chain Risk",
                "description": "Multi-tier supplier risk scoring + mitigation planning.",
                "steps": [
                    {"id": "supplier_graph", "name": "Supplier Graph",
                     "description": "Build upstream dependency graph"},
                    {"id": "concentration", "name": "Concentration Risk",
                     "description": "Score concentration by geo and tier"},
                    {"id": "disruption_sim", "name": "Disruption Simulation",
                     "description": "Run tabletop disruption scenarios"},
                    {"id": "mitigation", "name": "Mitigation Plan",
                     "description": "Produce actionable mitigations"},
                ],
            },
        ],
    },
]


# ── Realistic-looking log lines for synthetic work ─────────────────────
# Mirrors `_LOG_TEMPLATES` in the in-memory engine so the v2 UI looks
# identical against either backend.
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


def _sample_log_line(step_id: str, tick: int, total_ticks: int) -> str:
    template = random.choice(_LOG_TEMPLATES)
    return f"[{step_id}] {template.format(n=random.randint(8, 128))} (tick {tick}/{total_ticks})"


# ── Generic demo stage class ───────────────────────────────────────────
class DemoStage(BaseStage):
    """Synthetic ``BaseStage`` whose steps sleep and emit realistic logs.

    Subclasses override the three class-level constants
    (``STAGE_NAME``, ``STAGE_DESCRIPTION``, ``STEP_DEFINITIONS``); the
    rest is shared. ``register_demo_stages()`` builds these subclasses
    dynamically from ``DEMO_JOURNEYS`` so the registry stays in sync
    with the seed script's journey definitions automatically.

    Per-step behaviour:
    - Bounded random sleep (default 0.1-0.4s) per tick, configurable
      via the step's ``sleep_min`` / ``sleep_max`` keys.
    - 4-8 random ticks per step (override per-step with ``ticks=N``).
    - One ``stage_log("INFO", ...)`` per tick; the helper writes to
      the local log file, the DynamoDB LIVELOG buffer, AND broadcasts
      a ``log`` SSE event with the step_id — same path as production
      stages, so the v2 UI's terminal lights up identically.
    - Cooperative cancellation: ``self.is_cancelled()`` checked between
      ticks; if true, returns ``status="cancelled"`` instead of raising.
    - Optional failure injection: if a step's ``fail=True``, the step
      raises after its ticks complete with ``fail_reason`` as the error.
    """

    STAGE_NAME: str = "demo"
    STAGE_DESCRIPTION: str = "Demo stage"
    STEP_DEFINITIONS: List[Dict[str, Any]] = []

    def __init__(
        self,
        journey_id: str,
        stage_id: str,
        job_id: str,
        region_name: Optional[str] = None,
        role_arn: Optional[str] = None,
        # Accept (and ignore) the optional `enable_logging` kwarg the
        # executor passes when introspecting stage metadata. This avoids
        # needing the second-call fallback path in get_stage_info().
        enable_logging: bool = True,
    ) -> None:
        super().__init__(journey_id, stage_id, job_id, region_name, role_arn)
        if enable_logging:
            try:
                self.setup_enhanced_logging()
            except Exception:
                # Local-file logging is best-effort; never fail the stage on it.
                pass

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    @property
    def stage_description(self) -> str:
        return self.STAGE_DESCRIPTION

    @property
    def steps(self) -> List[Dict[str, Any]]:
        # The executor reads `step["id"]` and `step["name"]`; pass the rest
        # through verbatim so any extra metadata (description, etc.) is
        # available to UI clients that introspect the stage.
        return [{"id": s["id"], "name": s["name"], "description": s.get("description", "")}
                for s in self.STEP_DEFINITIONS]

    def execute_step(self, step_id: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        sd = next((s for s in self.STEP_DEFINITIONS if s["id"] == step_id), None)
        if sd is None:
            self.stage_log("ERROR", f"Unknown step {step_id} in stage {self.stage_id}", step_id)
            return {"status": "failed", "error": f"unknown step {step_id}"}

        ticks = int(sd.get("ticks", random.randint(4, 8)))
        sleep_min = float(sd.get("sleep_min", 0.1))
        sleep_max = float(sd.get("sleep_max", 0.4))

        self.stage_log("INFO", f"Starting {sd['name']} ({ticks} ticks, "
                                f"sleep {sleep_min}-{sleep_max}s)", step_id)
        items_processed = 0
        for tick in range(1, ticks + 1):
            if self.is_cancelled():
                self.stage_log("WARNING",
                                f"Cancellation observed at tick {tick}/{ticks}", step_id)
                return {"status": "cancelled", "ticks_completed": tick - 1,
                        "items_processed": items_processed}

            time.sleep(random.uniform(sleep_min, sleep_max))
            n = random.randint(8, 128)
            items_processed += n
            self.stage_log("INFO", _sample_log_line(step_id, tick, ticks), step_id)

        if sd.get("fail", False):
            reason = sd.get("fail_reason", "synthetic failure for stress testing")
            self.stage_log("ERROR", reason, step_id)
            # Raise so the executor records the step as failed and halts the job.
            raise RuntimeError(f"DemoStage step {step_id} failed: {reason}")

        result = {
            "status": "success",
            "items_processed": items_processed,
            "ticks_completed": ticks,
        }
        self.stage_log("INFO", f"Completed {sd['name']}: "
                                f"{items_processed} items across {ticks} ticks", step_id)
        return result


# ── Registry helpers ───────────────────────────────────────────────────
def _make_demo_stage_class(
    stage_id: str,
    stage_name: str,
    stage_description: str,
    step_definitions: List[Dict[str, Any]],
) -> Type[DemoStage]:
    """Manufacture a DemoStage subclass with the given metadata baked in.

    A factory rather than a single shared class so the executor's
    ``stage_class.__name__`` log line and any future metaclass-driven
    introspection see meaningful names per stage.
    """
    class _Stage(DemoStage):
        STAGE_NAME = stage_name
        STAGE_DESCRIPTION = stage_description
        STEP_DEFINITIONS = list(step_definitions)

    _Stage.__name__ = f"DemoStage_{stage_id}"
    _Stage.__qualname__ = _Stage.__name__
    return _Stage


def list_demo_stage_ids() -> List[str]:
    """Return every stage_id that ``register_demo_stages`` would register."""
    return [s["stage_id"] for j in DEMO_JOURNEYS for s in j["stages"]]


def register_demo_stages(*, registry_register=register_stage) -> List[str]:
    """Register one DemoStage subclass per stage in ``DEMO_JOURNEYS``.

    Idempotent: re-registering a stage_id replaces the previous class
    (matches ``register_stage()``'s dict-set semantics in
    :mod:`nexus_ai_engine.stages.registry`).

    Args:
        registry_register: Optional callable used to register each stage.
            Defaults to the module-level ``register_stage`` so test code
            can inject a different sink without monkey-patching.

    Returns:
        The list of stage_ids that were registered, in registration order.
    """
    registered: List[str] = []
    for journey in DEMO_JOURNEYS:
        for stage in journey["stages"]:
            cls = _make_demo_stage_class(
                stage_id=stage["stage_id"],
                stage_name=stage["name"],
                stage_description=stage.get("description", stage["name"]),
                step_definitions=stage["steps"],
            )
            registry_register(stage["stage_id"], cls)
            registered.append(stage["stage_id"])
    return registered
