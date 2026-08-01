# 000 — Nexus AI Engine Overview

**Version:** 0.3.0  
**Status:** Draft  
**Related:** [040 Tool Registry](./040-tool-registry-integration.md) · [041 Ontology Data Plane](./041-ontology-data-plane-api.md)

---

## Vision

**Nexus AI Engine** is a **standalone shared execution service** that accepts
many **DSL-defined journeys**, schedules them on a **distributed worker fleet**,
and runs **stages** and **steps** concurrently — where every step is a
**ReAct tool** loaded from the **AI Engine Tool Registry** (published Python
packages). Tools reach data through **`nexus-tool-sdk`**, calling ontology
**VDL** and **Connector** APIs over HTTP.

Callers (ontology Copilot UI, MCP clients, batch schedulers, other microservices)
**submit journeys**; the engine **executes** them with the same rigor as
nexus-sre's Executor: deterministic orchestration, retries, approvals,
verification, audit, and crash recovery — but **without LLM reasoning inside
the engine**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Submitters (clients)                            │
│  ontology UI · MCP · Schedules · SDK · Journey Studio UI            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ POST /executions  (Journey DSL)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   NEXUS AI ENGINE (compute plane)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Journey API │→ │ Execution    │→ │ Distributed Worker Pool │   │
│  │ + DSL Store │  │ Manager      │  │ (Temporal + asyncio)    │   │
│  └─────────────┘  └──────────────┘  └───────────┬─────────────┘   │
│         │                  │                     │                 │
│         ▼                  ▼                     ▼                 │
│  DynamoDB            State Machine          Tool Dispatcher       │
│  (journeys, runs,    (101-aligned)         (local registry +     │
│   executions)                               nexus-tool-sdk) ──────┼──► ontology
│  S3 (logs, reports)   SSE / CloudEvents                           │    VDL + Connector APIs
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Journey Studio UI (embedded + future SPA)              │
│  Manage DSL · Monitor runs · Approvals · Logs · Metrics             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mission

The AI Engine **owns execution** of business/AI journeys. It:

- Accepts journey definitions (YAML/JSON DSL) and execution submissions
- Compiles stages/steps into an **ExecutionGraph** (nexus-sre contract)
- Dispatches **ReAct tools** via the **local Tool Registry** (published packages + `nexus-tool-sdk`)
- Runs **many journeys concurrently** on horizontally scaled workers
- Persists all state in **DynamoDB** (+ S3 for artifacts)
- Exposes **REST, SSE, and MCP** for management and monitoring
- Ships a **UI** for operators to manage and observe running journeys

The AI Engine **never**:

- Generates plans or chooses remediation (that is Copilot/Planner in ontology UI)
- Calls LLMs during execution ticks (optional ReAct agent mode is separate from tick loop)
- Stores connector credentials (ontology Connector API holds secrets)
- Replace nexus-sre's infra-focused Executor (complementary service)

Ontology services **never** (in production):

- Execute published ReAct tools or DSL journeys — see [041](./041-ontology-data-plane-api.md)

---

## Relationship to Nexus-SRE Executor

| Dimension | nexus-sre Executor | Nexus AI Engine |
|-----------|-------------------|-----------------|
| **Input** | `PlannerResult` (LLM-produced plan) | `JourneyDefinition` (human/DSL-authored) |
| **Graph** | `ExecutionGraph` from planner | `ExecutionGraph` compiled from DSL |
| **Tools** | K8s, Prometheus, AWS infra tools | ReAct tool packages in AI Engine; data via ontology VDL/Connector APIs |
| **Storage** | PostgreSQL | DynamoDB + S3 |
| **Workers** | Temporal + background pods | Temporal + asyncio job pool (same pattern) |
| **UI** | nexus-sre React SPA (Incidents, Approvals) | Journey Studio (journeys, runs, schedules) |
| **Reasoning** | Planner (separate) | Copilot in nexus-backend (separate) |

Both implement the **same executor semantics** per ADR-001:
orchestration logic in the engine; Temporal (or equivalent) as durability shell.

---

## Core Concepts

### Journey

A versioned document describing a multi-stage business workflow.

```yaml
apiVersion: nexus.ai/v1
kind: Journey
metadata:
  id: order-to-cash-monitor
  version: 3
spec:
  display_name: Order-to-Cash Monitor
  stages:
    - id: entity_resolution
      steps: [...]
    - id: three_way_match
      steps: [...]
```

### Stage

A named phase within a journey. Stages run **sequentially** by default;
within a stage, steps may run sequentially, in parallel, or via `foreach`.

### Step

One **ReAct tool invocation**:

```yaml
- id: match_invoice
  tool: o2c_match_order_delivery_invoice
  params:
    opportunity_id: "$item.Opportunity_ID"
  retry:
    max_attempts: 3
  requires_approval: false
```

### Execution (runtime)

When a caller submits a journey, the engine creates an **Execution** record
(tracked in DynamoDB). An execution may run one or all stages depending on
submission mode (`full_journey` | `single_stage` | `dry_run`).

### Run / Job (legacy term)

Today the codebase uses **Job** for a single stage execution. The refactor
aligns terminology:

| Legacy (v0.1) | Target (v0.2+) |
|---------------|----------------|
| Job | StageRun |
| start_job_execution | submit_stage_run |
| TransformationJobExecutor | StageRunExecutor |

Both terms coexist during migration; specs use **StageRun**.

---

## Service Boundaries

### In scope (AI Engine owns)

- Journey DSL storage, validation, versioning
- Execution orchestration (graph, state machine, retries)
- Distributed worker scheduling and concurrency limits
- Tool dispatch to registry (with policy passthrough)
- Execution persistence (DynamoDB), logs/reports (S3)
- SSE event streaming and execution API
- Journey Studio UI (manage + monitor)
- MCP tools (`journey_tool`, `execution_tool`, `logs_and_reports_tool`)

### Out of scope (callers own)

- Tool implementations and registration (nexus-backend)
- LLM / Copilot planning (nexus-backend control plane)
- User authentication (host ingress / Cognito — engine trusts caller identity headers)
- Infra remediation (nexus-sre)

---

## Deployment Model

Standalone Kubernetes service (already scaffolded in `deploy/k8s/`):

- **API pod** — FastAPI + embedded UI static assets
- **Worker pod(s)** — Temporal workers + asyncio stage-run workers (same image, different entrypoint)
- **DynamoDB** — `ai-engine-{env}` table family
- **S3** — logs and reports buckets
- **IRSA** — pod identity for AWS access

Horizontally scalable: HPA on queue depth + in-flight execution count.

---

## Success Criteria

1. Submit **N journeys** concurrently; engine respects `max_concurrent_executions`
2. Each step invokes a **registered ReAct tool** with policy validation
3. **Crash recovery**: kill a worker mid-run; execution resumes from DynamoDB state
4. **UI** shows live progress for all running journeys via SSE
5. **Zero coupling** to nexus-backend process — HTTP boundary only for tools
6. **Spec parity** with nexus-sre executor FSM, retries, approvals (adapted subset)

---

## Open Questions

| # | Question | Proposed default |
|---|----------|------------------|
| 1 | Embed Tool Registry in-engine vs always remote? | Remote HTTP to nexus-backend; optional embedded adapter for tests |
| 2 | Temporal mandatory or asyncio-only for v1? | Temporal for production; asyncio for local/test |
| 3 | Multi-tenant isolation | `tenant_id` prefix on all DynamoDB keys |
| 4 | Journey DSL storage | DynamoDB journey records + S3 for large YAML blobs |
