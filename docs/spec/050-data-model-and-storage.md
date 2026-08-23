# 050 — Data Model & Storage

**Version:** 0.2.0  
**Status:** Draft  

---

## Purpose

Define DynamoDB tables, S3 buckets, and item schemas for Nexus AI Engine as a
standalone service with its **own database** — separate from nexus-backend
Postgres and nexus-sre Postgres.

---

## Storage Tiers

| Tier | Technology | Purpose | Retention |
|------|------------|---------|-----------|
| Operational | DynamoDB | Journeys, executions, state, approvals | 90 days hot |
| Artifacts | S3 | Logs, reports, large step results | 1 year |
| Prompts | DynamoDB | Prompt catalog + version history | Indefinite |
| Analytics | S3 + Athena (optional) | Export parquet for BI | 2 years |

---

## DynamoDB Tables

### Table: `ai-engine-journeys-{env}`

Single-table design (matches existing nexus-backend journey layout).

| PK | SK | Entity |
|----|-----|--------|
| `JOURNEY#{journey_id}` | `META#info` | Journey metadata |
| `JOURNEY#{journey_id}` | `VERSION#{n}` | JourneyDefinition snapshot |
| `JOURNEY#{journey_id}` | `META#latest` | Pointer to current version |
| `JOURNEY#{journey_id}` | `JOB#{order}#{stage}#{run_id}` | StageRun (legacy) |
| `JOURNEY#{journey_id}` | `SCHEDULE#{schedule_id}` | Batch schedule |
| `TENANT#{tenant_id}` | `JOURNEY#{journey_id}` | Tenant index |

**GSI1:** `entity_type` + `updated_at` — list journeys  
**GSI2:** `status` + `started_at` — running jobs index

### Table: `ai-engine-executions-{env}` (NEW)

| PK | SK | Entity |
|----|-----|--------|
| `TENANT#{tid}#EXEC#{id}` | `STATE#current` | ExecutionState (latest) |
| `TENANT#{tid}#EXEC#{id}` | `STATE#v{revision}` | Historical revisions (optional) |
| `TENANT#{tid}#EXEC#{id}` | `GRAPH#snapshot` | Compiled ExecutionGraph JSON |
| `TENANT#{tid}#EXEC#{id}` | `APPROVAL#{aid}` | Approval records |
| `TENANT#{tid}#EXEC#{id}` | `NODE#{node_id}#ATTEMPT#{n}` | Tool attempt audit |
| `TENANT#{tid}#EXECUTIONS` | `STATUS#{status}#TS#{iso}#{id}` | Status index |
| `COUNTER#global` | `RUNNING` | Admission counter |
| `LOCK#EXEC#{id}` | `WORKER#{wid}` | Tick lock (TTL) |
| `BREAKER#{tool_id}` | `STATE` | Circuit breaker |

**GSI1:** `journey_id` + `started_at` — executions per journey  
**GSI2:** `tenant_id` + `status` — tenant dashboard

### Table: `ai-engine-prompts-{env}`

Existing prompts catalog (unchanged from v0.1):

| PK | SK |
|----|-----|
| `PROMPT#{name}` | `VERSION#{n}` |
| `PROMPT#{name}` | `META#current` |
| `PROMPT#{name}` | `AUDIT#{ts}` |

---

## S3 Buckets

### `ai-engine-journey-logs-{env}`

```text
logs/{tenant_id}/{journey_id}/{execution_id}/{stage_id}/{step_id}.jsonl
```

Structured log lines (JSONL), streamed during execution, finalized on step complete.

### `ai-engine-journey-reports-{env}`

```text
reports/{tenant_id}/{journey_id}/{execution_id}/summary.json
reports/{tenant_id}/{journey_id}/{execution_id}/stage/{stage_id}.json
```

Aggregate KPIs for UI dashboard.

### `ai-engine-journey-dsl-{env}` (optional)

Large journey YAML blobs:

```text
dsl/{journey_id}/v{version}.yaml
```

---

## Entity Schemas

### JourneyRecord

```python
class JourneyRecord(BaseModel):
    journey_id: str
    tenant_id: str
    display_name: str
    description: str
    latest_version: int
    status: JourneyStatus          # active | archived
    labels: dict[str, str]
    trigger: str
    schedule: str | None
    created_at: datetime
    updated_at: datetime
    oda_component_type: str | None  # TMF ODA alignment
```

### ExecutionRecord (summary for list views)

```python
class ExecutionRecord(BaseModel):
    execution_id: UUID
    journey_id: str
    journey_version: int
    tenant_id: str
    status: ExecutionStatus
    current_stage_id: str | None
    progress_pct: float            # derived
    started_at: datetime | None
    finished_at: datetime | None
    submitted_by: str
    labels: dict[str, str]
```

### StageRunRecord (legacy compatibility)

Preserved for existing UI/API consumers:

```python
class StageRunRecord(BaseModel):
    job_id: str                    # legacy name
    journey_id: str
    stage_id: str
    order: int
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    metrics: dict                  # KPI counters
    execution_id: UUID | None      # link to new model
```

---

## Migration from v0.1 Schema

| v0.1 | v0.2 |
|------|------|
| Job items under `JOURNEY#` | Retained + `execution_id` backfill |
| No execution table | New `ai-engine-executions-{env}` |
| In-memory engine state | All state in DynamoDB |
| SSE in-process only | SSE + optional event archive to S3 |

Migration script: `scripts/migrate-v01-jobs-to-executions.py`

---

## Capacity Planning

| Dimension | Dev | Prod (initial) |
|-----------|-----|----------------|
| Journeys | 50 | 5,000 |
| Concurrent executions | 10 | 500 |
| DynamoDB RCU/WCU | On-demand | On-demand |
| S3 log volume | 1 GB/mo | 100 GB/mo |
| Item size limit | Graph snapshot < 400KB; overflow to S3 |

Large `ExecutionGraph` snapshots exceeding 400KB stored in S3 with pointer in DynamoDB.

---

## Backup & DR

| Resource | Strategy |
|----------|----------|
| DynamoDB | Point-in-time recovery enabled |
| S3 | Versioning + lifecycle to Glacier |
| Prompts | Export nightly to S3 |

---

## IAM Policy (engine role)

Scoped in `scripts/legacy-deploy/iam/` (existing):

- `dynamodb:*` on `ai-engine-*` tables
- `s3:*` on `ai-engine-journey-*` buckets
- `secretsmanager:GetSecretValue` for tool credential refs (if resolved in-engine)
- No access to nexus-backend tables

---

## Local / Test Adapters

| Adapter | Path | Use |
|---------|------|-----|
| InMemoryJourneyRepository | `adapters/inmemory/` | Unit tests |
| InMemoryExecutionRepository | `adapters/inmemory/` | Unit tests |
| Moto DynamoDB | `tests/integration/` | AWS adapter tests |
| FileSystemLogSink | `adapters/fs/` | Offline dev |

Contract tests parametrize across in-memory and DynamoDB implementations.
