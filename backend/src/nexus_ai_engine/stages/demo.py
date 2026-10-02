"""Demo stage implementations shipped with the library.

Provides ``BaseStage`` subclasses covering 50+ demo journeys the
in-memory engine seeds (the original 14 plus a supply-chain load set
for parallel worker testing). Each step
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
    {
        "name": "Customer Onboarding",
        "description": "Verify identity, provision accounts, and trigger welcome workflows.",
        "odaComponentType": "customer-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "identity_verify", "name": "Identity Verification",
                "description": "KYC checks and document validation.",
                "steps": [
                    {"id": "doc_upload", "name": "Document Intake",
                     "description": "Collect ID and proof-of-address"},
                    {"id": "ocr_extract", "name": "OCR Extraction",
                     "description": "Parse fields from uploaded documents"},
                    {"id": "sanctions_check", "name": "Sanctions Screening",
                     "description": "Screen against watchlists"},
                    {"id": "identity_score", "name": "Identity Score",
                     "description": "Compute verification confidence"},
                ],
            },
            {
                "stage_id": "account_setup", "name": "Account Setup",
                "description": "Create CRM account and billing profile.",
                "steps": [
                    {"id": "crm_create", "name": "CRM Account",
                     "description": "Create account in Salesforce"},
                    {"id": "billing_profile", "name": "Billing Profile",
                     "description": "Set payment method and tax info"},
                    {"id": "entitlements", "name": "Entitlements",
                     "description": "Assign product entitlements"},
                ],
            },
            {
                "stage_id": "welcome_flow", "name": "Welcome Flow",
                "description": "Send onboarding comms and schedule kickoff.",
                "steps": [
                    {"id": "welcome_email", "name": "Welcome Email",
                     "description": "Send personalized welcome sequence"},
                    {"id": "portal_access", "name": "Portal Access",
                     "description": "Provision self-service portal login"},
                    {"id": "kickoff_schedule", "name": "Kickoff Schedule",
                     "description": "Book onboarding call with CSM"},
                ],
            },
        ],
    },
    {
        "name": "Fraud Detection Pipeline",
        "description": "Score transactions in real time and route suspicious activity for review.",
        "odaComponentType": "risk-management",
        "priority": "critical",
        "stages": [
            {
                "stage_id": "transaction_scoring", "name": "Transaction Scoring",
                "description": "Feature enrichment and ML fraud scoring.",
                "steps": [
                    {"id": "enrich", "name": "Feature Enrichment",
                     "description": "Join device, geo, and velocity signals", "ticks": 3,
                     "sleep_min": 0.05, "sleep_max": 0.12},
                    {"id": "score", "name": "Fraud Score",
                     "description": "Run gradient-boosted fraud model", "ticks": 3,
                     "sleep_min": 0.05, "sleep_max": 0.12},
                    {"id": "rules", "name": "Rules Engine",
                     "description": "Apply hard-block and velocity rules"},
                    {"id": "route", "name": "Case Routing",
                     "description": "Route high-risk txns to review queue"},
                ],
            },
            {
                "stage_id": "case_review", "name": "Case Review",
                "description": "Analyst review workflow for flagged transactions.",
                "steps": [
                    {"id": "case_create", "name": "Create Case",
                     "description": "Open fraud case with evidence bundle"},
                    {"id": "analyst_queue", "name": "Analyst Queue",
                     "description": "Assign to tier-1 analyst pool"},
                    {"id": "disposition", "name": "Disposition",
                     "description": "Record approve/decline decision"},
                ],
            },
        ],
    },
    {
        "name": "Billing Reconciliation",
        "description": "Match invoices to contracts and apply payments across ledgers.",
        "odaComponentType": "billing-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "invoice_match", "name": "Invoice Matching",
                "description": "Three-way match invoices against POs and receipts.",
                "steps": [
                    {"id": "invoice_ingest", "name": "Invoice Ingest",
                     "description": "Pull invoices from AP gateway"},
                    {"id": "po_match", "name": "PO Match",
                     "description": "Match line items to purchase orders"},
                    {"id": "variance_check", "name": "Variance Check",
                     "description": "Flag qty/price mismatches"},
                ],
            },
            {
                "stage_id": "payment_apply", "name": "Payment Application",
                "description": "Apply remittances and post to GL.",
                "steps": [
                    {"id": "remittance_parse", "name": "Remittance Parse",
                     "description": "Parse bank remittance files"},
                    {"id": "payment_match", "name": "Payment Match",
                     "description": "Match payments to open invoices"},
                    {"id": "gl_post", "name": "GL Posting",
                     "description": "Post journal entries to ERP"},
                ],
            },
        ],
    },
    {
        "name": "Network Capacity Planning",
        "description": "Forecast traffic growth and recommend capacity upgrades by region.",
        "odaComponentType": "resource-management",
        "priority": "medium",
        "stages": [
            {
                "stage_id": "traffic_ingest", "name": "Traffic Ingest",
                "description": "Collect SNMP and flow telemetry.",
                "steps": [
                    {"id": "snmp_poll", "name": "SNMP Poll",
                     "description": "Poll router/switch counters"},
                    {"id": "flow_collect", "name": "Flow Collection",
                     "description": "Aggregate NetFlow records"},
                    {"id": "normalize", "name": "Normalize",
                     "description": "Normalize to common schema"},
                ],
            },
            {
                "stage_id": "capacity_model", "name": "Capacity Model",
                "description": "Project utilization and headroom.",
                "steps": [
                    {"id": "baseline", "name": "Baseline Utilization",
                     "description": "Compute 30-day baseline per link"},
                    {"id": "growth_forecast", "name": "Growth Forecast",
                     "description": "Project 90-day traffic growth"},
                    {"id": "headroom", "name": "Headroom Analysis",
                     "description": "Identify links below threshold"},
                ],
            },
            {
                "stage_id": "capacity_recommend", "name": "Recommendations",
                "description": "Generate upgrade and augmentation plans.",
                "steps": [
                    {"id": "upgrade_plan", "name": "Upgrade Plan",
                     "description": "Recommend bandwidth upgrades"},
                    {"id": "cost_estimate", "name": "Cost Estimate",
                     "description": "Estimate capex for upgrades"},
                    {"id": "publish_report", "name": "Publish Report",
                     "description": "Publish capacity report to ops portal"},
                ],
            },
        ],
    },
    {
        "name": "Product Catalog Sync",
        "description": "Extract product data from PIM and publish to commerce channels.",
        "odaComponentType": "product-management",
        "priority": "medium",
        "stages": [
            {
                "stage_id": "catalog_extract", "name": "Catalog Extract",
                "description": "Pull SKU master and attributes from PIM.",
                "steps": [
                    {"id": "sku_pull", "name": "SKU Pull",
                     "description": "Extract active SKU catalog"},
                    {"id": "attr_map", "name": "Attribute Mapping",
                     "description": "Map PIM attributes to channel schema"},
                    {"id": "media_sync", "name": "Media Sync",
                     "description": "Sync product images and assets"},
                ],
            },
            {
                "stage_id": "catalog_publish", "name": "Catalog Publish",
                "description": "Validate and push to downstream channels.",
                "steps": [
                    {"id": "validate", "name": "Schema Validation",
                     "description": "Validate against channel constraints"},
                    {"id": "delta_compute", "name": "Delta Compute",
                     "description": "Compute changed SKUs since last sync"},
                    {"id": "channel_push", "name": "Channel Push",
                     "description": "Push catalog delta to commerce APIs", "ticks": 3,
                     "sleep_min": 0.05, "sleep_max": 0.12},
                ],
            },
        ],
    },
    {
        "name": "SLA Monitoring",
        "description": "Collect service metrics and detect SLA breaches across contracts.",
        "odaComponentType": "service-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "metric_collect", "name": "Metric Collection",
                "description": "Pull uptime and latency metrics from observability stack.",
                "steps": [
                    {"id": "uptime_pull", "name": "Uptime Pull",
                     "description": "Query uptime from Prometheus"},
                    {"id": "latency_pull", "name": "Latency Pull",
                     "description": "Query p95 latency by service"},
                    {"id": "aggregate", "name": "Aggregate",
                     "description": "Roll up per-contract SLA windows"},
                ],
            },
            {
                "stage_id": "breach_detect", "name": "Breach Detection",
                "description": "Compare metrics to contractual thresholds.",
                "steps": [
                    {"id": "threshold_check", "name": "Threshold Check",
                     "description": "Compare metrics to SLA targets"},
                    {"id": "breach_alert", "name": "Breach Alert",
                     "description": "Open incidents for breached SLAs"},
                    {"id": "credit_calc", "name": "Credit Calculation",
                     "description": "Compute service credits owed"},
                ],
            },
        ],
    },
    {
        "name": "Churn Prediction",
        "description": "Score at-risk accounts and generate retention outreach plans.",
        "odaComponentType": "customer-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "churn_features", "name": "Feature Build",
                "description": "Assemble behavioral and usage features.",
                "steps": [
                    {"id": "usage_agg", "name": "Usage Aggregation",
                     "description": "Aggregate 90-day product usage"},
                    {"id": "support_signals", "name": "Support Signals",
                     "description": "Pull ticket volume and CSAT trends"},
                    {"id": "billing_signals", "name": "Billing Signals",
                     "description": "Detect payment failures and downgrades"},
                ],
            },
            {
                "stage_id": "churn_score", "name": "Churn Scoring",
                "description": "Run ML model and segment accounts.",
                "steps": [
                    {"id": "model_run", "name": "Model Run",
                     "description": "Score churn probability per account", "ticks": 3,
                     "sleep_min": 0.05, "sleep_max": 0.12},
                    {"id": "segment", "name": "Risk Segmentation",
                     "description": "Bucket into high/medium/low risk"},
                    {"id": "explain", "name": "Explainability",
                     "description": "Extract top churn drivers per account"},
                ],
            },
            {
                "stage_id": "retention_outreach", "name": "Retention Outreach",
                "description": "Generate and queue retention playbooks.",
                "steps": [
                    {"id": "playbook_select", "name": "Playbook Select",
                     "description": "Match account to retention playbook"},
                    {"id": "offer_gen", "name": "Offer Generation",
                     "description": "Generate personalized retention offer"},
                    {"id": "outreach_queue", "name": "Outreach Queue",
                     "description": "Queue CSM outreach tasks"},
                ],
            },
        ],
    },
    {
        "name": "Partner Settlement",
        "description": "Aggregate partner usage and calculate revenue-share settlements.",
        "odaComponentType": "billing-management",
        "priority": "medium",
        "stages": [
            {
                "stage_id": "usage_aggregate", "name": "Usage Aggregation",
                "description": "Roll up partner API and transaction usage.",
                "steps": [
                    {"id": "api_meter", "name": "API Metering",
                     "description": "Aggregate API call volumes"},
                    {"id": "txn_meter", "name": "Transaction Metering",
                     "description": "Sum transaction volumes by partner"},
                    {"id": "rate_apply", "name": "Rate Application",
                     "description": "Apply contract rate cards"},
                ],
            },
            {
                "stage_id": "settlement_calc", "name": "Settlement Calculation",
                "description": "Compute revenue share and generate statements.",
                "steps": [
                    {"id": "rev_share", "name": "Revenue Share",
                     "description": "Calculate partner revenue share"},
                    {"id": "adjustments", "name": "Adjustments",
                     "description": "Apply credits and chargebacks"},
                    {"id": "statement_gen", "name": "Statement Generation",
                     "description": "Generate settlement statement PDF"},
                ],
            },
        ],
    },
    {
        "name": "Quote-to-Order",
        "description": "Convert sales quotes into validated orders across CPQ and ERP.",
        "odaComponentType": "order-management",
        "priority": "high",
        "stages": [
            {
                "stage_id": "quote_validate", "name": "Quote Validation",
                "description": "Validate pricing, discounts, and product availability.",
                "steps": [
                    {"id": "price_check", "name": "Price Check",
                     "description": "Validate list and negotiated prices"},
                    {"id": "discount_audit", "name": "Discount Audit",
                     "description": "Verify discount within approval limits"},
                    {"id": "availability", "name": "Availability Check",
                     "description": "Check inventory and lead times"},
                ],
            },
            {
                "stage_id": "order_create", "name": "Order Creation",
                "description": "Create ERP sales order from approved quote.",
                "steps": [
                    {"id": "order_build", "name": "Order Build",
                     "description": "Map quote lines to ERP order"},
                    {"id": "credit_check", "name": "Credit Check",
                     "description": "Run customer credit hold check"},
                    {"id": "order_submit", "name": "Order Submit",
                     "description": "Submit order to fulfillment", "ticks": 3,
                     "sleep_min": 0.05, "sleep_max": 0.12},
                ],
            },
            {
                "stage_id": "fulfillment_handoff", "name": "Fulfillment Handoff",
                "description": "Notify warehouse and update CRM opportunity.",
                "steps": [
                    {"id": "wms_notify", "name": "WMS Notify",
                     "description": "Send pick list to warehouse"},
                    {"id": "crm_update", "name": "CRM Update",
                     "description": "Close-won opportunity in CRM"},
                    {"id": "customer_notify", "name": "Customer Notify",
                     "description": "Send order confirmation email"},
                ],
            },
        ],
    },
]


def _sc_steps(pairs: List[tuple]) -> List[Dict[str, Any]]:
    """Compact supply-chain steps — short ticks so 50 journeys can run in parallel."""
    return [
        {
            "id": step_id,
            "name": name,
            "description": desc,
            "ticks": 3,
            "sleep_min": 0.05,
            "sleep_max": 0.12,
        }
        for step_id, name, desc in pairs
    ]


def _sc_journey(
    name: str,
    description: str,
    oda: str,
    priority: str,
    stages: List[tuple],
) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "odaComponentType": oda,
        "priority": priority,
        "stages": [
            {
                "stage_id": stage_id,
                "name": stage_name,
                "description": stage_desc,
                "steps": _sc_steps(steps),
            }
            for stage_id, stage_name, stage_desc, steps in stages
        ],
    }


def _supply_chain_load_journeys() -> List[Dict[str, Any]]:
    """Extra supply-chain journeys for parallel Run-all load tests."""
    return [
        _sc_journey(
            "Inbound ASN Reconciliation",
            "Match inbound ASNs to POs and goods receipts at the DC door.",
            "inventory-management", "high",
            [("inbound_asn", "ASN Reconciliation", "Match ASN lines to PO and GRN.", [
                ("asn_ingest", "ASN Ingest", "Pull ASNs from EDI 856"),
                ("po_align", "PO Align", "Align ASN lines to open POs"),
                ("variance", "Variance Flag", "Flag qty and SKU mismatches"),
            ])],
        ),
        _sc_journey(
            "Yard Gate-In Control",
            "Check in trailers, assign yard spots, and release to dock.",
            "resource-management", "medium",
            [("yard_gate", "Yard Gate-In", "Trailer check-in and spot assignment.", [
                ("trailer_scan", "Trailer Scan", "Read RFID and appointment id"),
                ("spot_assign", "Spot Assign", "Assign yard parking spot"),
                ("dock_release", "Dock Release", "Release trailer to dock queue"),
            ])],
        ),
        _sc_journey(
            "Dock Appointment Optimizer",
            "Build daily dock calendars from carrier appointments and labor.",
            "resource-management", "high",
            [("dock_sched", "Dock Scheduling", "Optimize door assignments by window.", [
                ("appt_ingest", "Appointment Ingest", "Load carrier appointment requests"),
                ("labor_fit", "Labor Fit", "Match doors to available labor"),
                ("calendar_pub", "Calendar Publish", "Publish dock calendar to WMS"),
            ])],
        ),
        _sc_journey(
            "Cross-Dock Flow Control",
            "Match inbound pallets to outbound waves without putaway.",
            "inventory-management", "high",
            [("cross_dock", "Cross-Dock Control", "Inbound-to-outbound pallet matching.", [
                ("inbound_sort", "Inbound Sort", "Sort pallets by outbound destination"),
                ("wave_match", "Wave Match", "Match pallets to staged waves"),
                ("bypass_putaway", "Bypass Putaway", "Route matched pallets to staging"),
            ])],
        ),
        _sc_journey(
            "Wave Planning Engine",
            "Release pick waves by carrier cutoff, SLA, and aisle congestion.",
            "order-management", "high",
            [("wave_plan", "Wave Planning", "Build and release pick waves.", [
                ("order_batch", "Order Batch", "Group orders by cutoff and zone"),
                ("congestion", "Congestion Check", "Score aisle congestion risk"),
                ("wave_release", "Wave Release", "Release wave to WMS"),
            ])],
        ),
        _sc_journey(
            "Pick-Path Optimization",
            "Sequence picks to cut travel time across pick faces.",
            "inventory-management", "medium",
            [("pick_path", "Pick-Path Optimizer", "Travel-minimizing pick sequences.", [
                ("slot_load", "Slot Load", "Load pick-face coordinates"),
                ("path_solve", "Path Solve", "Compute shortest pick tour"),
                ("task_push", "Task Push", "Push sequenced tasks to RF"),
            ])],
        ),
        _sc_journey(
            "Pack-and-Ship QA",
            "Validate carton contents, labels, and carrier compliance before ship.",
            "order-management", "medium",
            [("pack_ship", "Pack and Ship QA", "Carton QA and label compliance.", [
                ("scan_verify", "Scan Verify", "Verify SKU and qty in carton"),
                ("label_check", "Label Check", "Validate GS1 and carrier labels"),
                ("manifest", "Manifest", "Add carton to carrier manifest"),
            ])],
        ),
        _sc_journey(
            "Last-Mile Route Optimization",
            "Build delivery routes from stop density, windows, and vehicle capacity.",
            "resource-management", "high",
            [("last_mile", "Last-Mile Routing", "VRP solve for same-day delivery.", [
                ("stop_cluster", "Stop Cluster", "Cluster stops by geo and window"),
                ("route_solve", "Route Solve", "Assign stops to vehicles"),
                ("eta_pub", "ETA Publish", "Publish ETAs to customer portal"),
            ])],
        ),
        _sc_journey(
            "Carrier Tendering Desk",
            "Tender loads, collect bids, and award carriers by cost and OTIF.",
            "resource-management", "high",
            [("carrier_tender", "Carrier Tendering", "Spot and contract tender flow.", [
                ("load_build", "Load Build", "Build tender packages from orders"),
                ("bid_collect", "Bid Collect", "Collect carrier quotes"),
                ("award", "Award", "Award load to best cost/OTIF bid"),
            ])],
        ),
        _sc_journey(
            "Freight Audit and Pay",
            "Audit carrier invoices against contracted rates and pay approved bills.",
            "billing-management", "medium",
            [("freight_audit", "Freight Audit", "Rate audit and invoice payment.", [
                ("invoice_load", "Invoice Load", "Ingest carrier freight invoices"),
                ("rate_audit", "Rate Audit", "Compare billed vs contracted rates"),
                ("pay_release", "Pay Release", "Release approved invoices to AP"),
            ])],
        ),
        _sc_journey(
            "Detention and Demurrage Desk",
            "Detect container/trailer dwell overages and raise claims.",
            "billing-management", "medium",
            [("detention_dm", "Detention Desk", "Dwell overage detection and claims.", [
                ("dwell_track", "Dwell Track", "Track gate-in to gate-out dwell"),
                ("overage_flag", "Overage Flag", "Flag detention and demurrage"),
                ("claim_open", "Claim Open", "Open carrier claim cases"),
            ])],
        ),
        _sc_journey(
            "Returns Disposition Engine",
            "Grade returned goods and route to restock, refurb, or scrap.",
            "inventory-management", "medium",
            [("returns_disp", "Returns Disposition", "Grade and route returned units.", [
                ("rma_ingest", "RMA Ingest", "Pull open RMAs from OMS"),
                ("grade", "Grade", "Inspect and grade returned units"),
                ("route_disp", "Route Disposition", "Restock, refurb, or scrap"),
            ])],
        ),
        _sc_journey(
            "Reverse Logistics Routing",
            "Plan return-to-vendor and return-to-DC moves by cost and recovery.",
            "resource-management", "medium",
            [("reverse_log", "Reverse Logistics", "Return move planning.", [
                ("origin_group", "Origin Group", "Group returns by origin DC"),
                ("lane_cost", "Lane Cost", "Score RTV vs RTC lanes"),
                ("move_book", "Move Book", "Book reverse freight"),
            ])],
        ),
        _sc_journey(
            "Cold-Chain Temperature Monitor",
            "Watch reefer telemetry and escalate temperature excursions.",
            "resource-management", "critical",
            [("cold_chain", "Cold-Chain Monitor", "Reefer telemetry and excursion alerts.", [
                ("telem_pull", "Telemetry Pull", "Pull reefer sensor streams"),
                ("excursions", "Excursion Detect", "Flag out-of-range intervals"),
                ("escalate", "Escalate", "Notify QA and carrier ops"),
            ])],
        ),
        _sc_journey(
            "Hazardous Goods Compliance",
            "Validate hazmat docs, placards, and segregation before dispatch.",
            "resource-management", "critical",
            [("hazmat_comp", "Hazmat Compliance", "DG documentation and segregation.", [
                ("un_class", "UN Classify", "Confirm UN numbers and packing groups"),
                ("segregate", "Segregate", "Check incompatible load mixing"),
                ("docs_ok", "Docs Check", "Validate SDS and placards"),
            ])],
        ),
        _sc_journey(
            "Customs Clearance Brokerage",
            "Classify HS codes, compute duties, and file import entries.",
            "order-management", "high",
            [("customs_clr", "Customs Clearance", "Import classification and entry.", [
                ("hs_class", "HS Classify", "Assign HS codes to SKUs"),
                ("duty_calc", "Duty Calc", "Compute duties and VAT"),
                ("entry_file", "Entry File", "File entry with broker"),
            ])],
        ),
        _sc_journey(
            "Trade Preference Qualification",
            "Qualify shipments for FTA preference and generate certificates.",
            "order-management", "medium",
            [("trade_pref", "Trade Preference", "FTA qualification and certificates.", [
                ("origin_rule", "Origin Rule", "Apply product-specific origin rules"),
                ("qualify", "Qualify", "Mark eligible preference claims"),
                ("cert_issue", "Certificate", "Issue COO / Form A"),
            ])],
        ),
        _sc_journey(
            "Incoming Inspection Sampling",
            "Sample inbound lots and hold or release based on AQL.",
            "inventory-management", "high",
            [("incoming_qc", "Incoming Inspection", "AQL sampling and lot hold/release.", [
                ("lot_select", "Lot Select", "Select lots due for inspection"),
                ("aql_sample", "AQL Sample", "Draw sample per AQL plan"),
                ("hold_release", "Hold or Release", "Hold failed lots, release pass"),
            ])],
        ),
        _sc_journey(
            "Cycle Count Reconciliation",
            "Run ABC cycle counts and post inventory adjustments.",
            "inventory-management", "medium",
            [("cycle_count", "Cycle Count", "ABC counts and variance posting.", [
                ("count_gen", "Count Generate", "Generate ABC count lists"),
                ("variance_calc", "Variance Calc", "Compare counted vs book qty"),
                ("adjust_post", "Adjust Post", "Post approved adjustments"),
            ])],
        ),
        _sc_journey(
            "Slotting Optimization",
            "Re-slot fast movers to golden zones from velocity and cube.",
            "inventory-management", "medium",
            [("slotting_opt", "Slotting Optimizer", "Velocity-based re-slotting.", [
                ("velocity", "Velocity Rank", "Rank SKUs by pick velocity"),
                ("cube_fit", "Cube Fit", "Fit SKUs to pick-face cube"),
                ("move_list", "Move List", "Publish re-slot move list"),
            ])],
        ),
        _sc_journey(
            "Multi-Echelon Inventory Plan",
            "Set stock targets across plants, DCs, and stores as one network.",
            "inventory-management", "high",
            [("mei_plan", "Multi-Echelon Plan", "Network inventory targets.", [
                ("node_demand", "Node Demand", "Roll demand to each echelon"),
                ("target_set", "Target Set", "Set min/max per node"),
                ("push_pull", "Push Pull", "Recommend transfers and buys"),
            ])],
        ),
        _sc_journey(
            "Transfer Order Balancing",
            "Balance overstock and stockouts with inter-DC transfers.",
            "inventory-management", "medium",
            [("xfer_balance", "Transfer Balancing", "Inter-DC surplus-to-need moves.", [
                ("surplus", "Surplus Detect", "Find overstock nodes"),
                ("need_match", "Need Match", "Match surplus to short nodes"),
                ("to_create", "TO Create", "Create transfer orders"),
            ])],
        ),
        _sc_journey(
            "Expedite Exception Desk",
            "Identify late POs and recommend expedite or split-ship actions.",
            "order-management", "high",
            [("expedite_desk", "Expedite Desk", "Late PO exception handling.", [
                ("late_scan", "Late Scan", "Find POs past promise date"),
                ("option_score", "Option Score", "Score expedite vs split-ship"),
                ("action_queue", "Action Queue", "Queue buyer actions"),
            ])],
        ),
        _sc_journey(
            "OTIF Scorecard",
            "Compute on-time in-full by supplier, lane, and customer.",
            "party-management", "high",
            [("otif_score", "OTIF Scorecard", "On-time in-full scorecards.", [
                ("ship_join", "Shipment Join", "Join ASN, receipt, and promise"),
                ("otif_calc", "OTIF Calc", "Compute OTIF by dimension"),
                ("scorecard", "Scorecard Publish", "Publish supplier scorecards"),
            ])],
        ),
        _sc_journey(
            "Supplier OTIF Coaching",
            "Turn OTIF misses into supplier corrective-action plans.",
            "party-management", "medium",
            [("supplier_otif", "Supplier Coaching", "CAPA plans from OTIF misses.", [
                ("miss_cluster", "Miss Cluster", "Cluster OTIF misses by root cause"),
                ("capa_draft", "CAPA Draft", "Draft corrective actions"),
                ("supplier_send", "Supplier Send", "Send CAPA to supplier portal"),
            ])],
        ),
        _sc_journey(
            "Port Congestion Watch",
            "Score port dwell and reroute bookings away from congested terminals.",
            "resource-management", "high",
            [("port_congest", "Port Congestion", "Port dwell scoring and reroute.", [
                ("ais_dwell", "AIS Dwell", "Measure vessel and yard dwell"),
                ("congest_score", "Congest Score", "Score terminals by delay"),
                ("reroute", "Reroute", "Recommend alternate ports"),
            ])],
        ),
        _sc_journey(
            "Vessel Schedule Integrity",
            "Detect rolled bookings and rebook containers to the next vessel.",
            "resource-management", "medium",
            [("vessel_sked", "Vessel Schedule", "Rolled-booking detection and rebook.", [
                ("sked_pull", "Schedule Pull", "Pull carrier vessel schedules"),
                ("roll_detect", "Roll Detect", "Find rolled container bookings"),
                ("rebook", "Rebook", "Rebook to next available vessel"),
            ])],
        ),
        _sc_journey(
            "Container Utilization Planner",
            "Maximize TEU fill and reduce empty repositioning.",
            "resource-management", "medium",
            [("container_util", "Container Utilization", "TEU fill and empty reposition.", [
                ("fill_calc", "Fill Calc", "Compute cube and weight fill"),
                ("empty_repo", "Empty Reposition", "Plan empty container moves"),
                ("load_plan", "Load Plan", "Publish container load plans"),
            ])],
        ),
        _sc_journey(
            "Pallet Build Optimizer",
            "Build stable mixed pallets from cube, crush, and store constraints.",
            "inventory-management", "medium",
            [("pallet_build", "Pallet Build", "Mixed-pallet optimization.", [
                ("cube_pack", "Cube Pack", "Pack cartons into pallet cube"),
                ("crush_check", "Crush Check", "Respect crush and stacking rules"),
                ("label_build", "Label Build", "Generate SSCC pallet labels"),
            ])],
        ),
        _sc_journey(
            "Fuel Surcharge Recalc",
            "Recalculate fuel surcharge on open tenders from weekly indices.",
            "billing-management", "low",
            [("fuel_surcharge", "Fuel Surcharge", "Index-based fuel recalc.", [
                ("index_pull", "Index Pull", "Pull DOE / platts fuel index"),
                ("rate_recalc", "Rate Recalc", "Recalc surcharge on open loads"),
                ("invoice_adj", "Invoice Adjust", "Post surcharge adjustments"),
            ])],
        ),
        _sc_journey(
            "Carbon Emissions Ledger",
            "Estimate shipment CO2e and allocate emissions to customers.",
            "data-pipeline", "medium",
            [("carbon_ledger", "Carbon Ledger", "Shipment CO2e estimation.", [
                ("lane_factor", "Lane Factor", "Apply mode and lane emission factors"),
                ("co2_alloc", "CO2 Allocate", "Allocate CO2e to shippers"),
                ("ledger_post", "Ledger Post", "Post to emissions ledger"),
            ])],
        ),
        _sc_journey(
            "Packaging Compliance Check",
            "Validate packaging against retailer and channel requirements.",
            "product-management", "medium",
            [("pack_comply", "Packaging Compliance", "Retailer pack-spec validation.", [
                ("spec_load", "Spec Load", "Load retailer packaging specs"),
                ("dim_check", "Dim Check", "Check carton dims and barcode"),
                ("reject_flag", "Reject Flag", "Flag non-compliant SKUs"),
            ])],
        ),
        _sc_journey(
            "Serial Traceability Recall",
            "Trace serialized lots forward and reverse for recall scope.",
            "product-management", "critical",
            [("serial_recall", "Serial Recall", "Forward and reverse lot trace.", [
                ("serial_lookup", "Serial Lookup", "Find affected serials and lots"),
                ("fwd_trace", "Forward Trace", "Trace to customer shipments"),
                ("hold_notify", "Hold Notify", "Hold stock and notify customers"),
            ])],
        ),
        _sc_journey(
            "Lot Expiry Allocation",
            "Allocate soon-to-expire lots first and block expired stock.",
            "inventory-management", "high",
            [("lot_expiry", "Lot Expiry Allocation", "FEFO allocation and expiry block.", [
                ("expiry_scan", "Expiry Scan", "Find lots near expiry"),
                ("fefo_alloc", "FEFO Allocate", "Allocate oldest eligible lots"),
                ("block_exp", "Block Expired", "Block expired lots from pick"),
            ])],
        ),
        _sc_journey(
            "Promotional Display Replenish",
            "Replenish store displays from DC based on promo calendar lift.",
            "inventory-management", "medium",
            [("promo_replen", "Promo Replenish", "Display replenishment from promo lift.", [
                ("promo_cal", "Promo Calendar", "Load active promo events"),
                ("lift_qty", "Lift Qty", "Compute display replenish qty"),
                ("store_push", "Store Push", "Create store replenish orders"),
            ])],
        ),
        _sc_journey(
            "Spare Parts Kitting",
            "Kit service parts against work orders and ship to field techs.",
            "inventory-management", "medium",
            [("spare_kit", "Spare Parts Kitting", "Work-order kitting for field service.", [
                ("wo_pull", "WO Pull", "Pull open field work orders"),
                ("kit_build", "Kit Build", "Reserve and kit BOM parts"),
                ("tech_ship", "Tech Ship", "Ship kits to technician locations"),
            ])],
        ),
        _sc_journey(
            "Aftermarket Parts Fulfillment",
            "Promise and ship aftermarket parts from the service network.",
            "order-management", "medium",
            [("aftermarket", "Aftermarket Fulfillment", "Service-parts ATP and ship.", [
                ("atp_check", "ATP Check", "Check available-to-promise"),
                ("src_select", "Source Select", "Pick fulfilling service DC"),
                ("parts_ship", "Parts Ship", "Create and ship parts order"),
            ])],
        ),
        _sc_journey(
            "Contract Manufacturing MRP",
            "Explode CMO demand, check component ATP, and release POs.",
            "order-management", "high",
            [("cmo_mrp", "CMO MRP", "Contract-manufacturer material plan.", [
                ("bom_explode", "BOM Explode", "Explode CMO finished-good demand"),
                ("comp_atp", "Component ATP", "Check component availability"),
                ("po_release", "PO Release", "Release component POs to CMO"),
            ])],
        ),
        _sc_journey(
            "Supplier ASN Quality Gate",
            "Score inbound ASNs for completeness before they hit the yard.",
            "party-management", "medium",
            [("supplier_asn", "Supplier ASN Gate", "ASN completeness scoring.", [
                ("asn_complete", "Completeness", "Score missing SSCC and dates"),
                ("early_late", "Early Late", "Flag early/late arrival risk"),
                ("gate_hold", "Gate Hold", "Hold incomplete ASNs at gate"),
            ])],
        ),
        _sc_journey(
            "Safety Stock Recalibration",
            "Recalibrate safety stock from demand variance and lead-time drift.",
            "inventory-management", "medium",
            [("ss_recal", "Safety Stock Recal", "Periodic safety-stock refresh.", [
                ("var_est", "Variance Estimate", "Estimate demand variance"),
                ("lt_drift", "Lead-Time Drift", "Detect supplier LT drift"),
                ("ss_update", "SS Update", "Write new safety-stock targets"),
            ])],
        ),
    ]


DEMO_JOURNEYS = list(DEMO_JOURNEYS) + _supply_chain_load_journeys()


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
