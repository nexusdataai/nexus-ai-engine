# 021 — Execution State Machine

**Version:** 0.2.0  
**Status:** Draft  
**Aligns with:** [nexus-sre/101-execution-state-machine](../../nexus-sre/docs/executor/101-execution-state-machine.md)

---

## Purpose

Define the **authoritative state machines** for:

1. **Execution** — top-level journey run
2. **StageRun** — single stage invocation (legacy: Job)
3. **Node (Step)** — individual graph node

---

## Execution State Machine

```text
                    ┌──────────┐
                    │ PENDING  │
                    └────┬─────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             │
    ┌──────────────┐  ┌────────┐       │
    │ AWAITING_    │  │ RUNNING│◄──────┤ resume
    │ APPROVAL     │  └───┬────┘       │
    └──────┬───────┘      │            │
           │              ├────────────┼──► PAUSED
           │              ▼            │
           │         ┌──────────┐     │
           │         │VERIFYING │     │
           │         └────┬─────┘     │
           │              │            │
           │    ┌─────────┼─────────┐  │
           │    ▼         ▼         ▼  │
           │ SUCCEEDED  FAILED   TIMED_OUT
           │              │
           │              ▼
           │      ┌───────────────┐
           │      │ROLLBACK_      │
           │      │PENDING        │
           │      └───────┬───────┘
           │              ▼
           │      ┌───────────────┐
           └─────►│ ROLLING_BACK  │──► FAILED (terminal)
                  └───────────────┘

    Any non-terminal ──cancel──► CANCELLED
```

### States

| State | Meaning |
|-------|---------|
| `PENDING` | Created, workflow not started |
| `AWAITING_APPROVAL` | Blocked on human approval |
| `RUNNING` | Actively dispatching steps |
| `PAUSED` | Operator pause; no new dispatches |
| `VERIFYING` | Stage-level verification in progress |
| `SUCCEEDED` | All stages completed successfully |
| `FAILED` | Unrecoverable failure |
| `CANCELLED` | Operator cancelled |
| `TIMED_OUT` | Exceeded `max_wall_clock_s` |
| `ROLLBACK_PENDING` | Failure triggered rollback |
| `ROLLING_BACK` | Executing rollback steps |

### Transitions (selected)

| From | Event | To |
|------|-------|-----|
| PENDING | workflow_started | RUNNING |
| PENDING | approval_required | AWAITING_APPROVAL |
| AWAITING_APPROVAL | approved | RUNNING |
| AWAITING_APPROVAL | rejected | FAILED |
| RUNNING | all_stage_nodes_done | VERIFYING |
| VERIFYING | verification_passed | SUCCEEDED |
| VERIFYING | verification_failed | ROLLBACK_PENDING |
| RUNNING | node_failed (abort policy) | ROLLBACK_PENDING |
| ROLLBACK_PENDING | rollback_started | ROLLING_BACK |
| ROLLING_BACK | rollback_done | FAILED |

---

## Node (Step) State Machine

```text
PENDING → READY → RUNNING → SUCCEEDED
                    │    └──► FAILED → (retry) → RUNNING
                    │    └──► SKIPPED (condition false)
                    └──► ROLLED_BACK
```

| State | Meaning |
|-------|---------|
| `PENDING` | Waiting on dependencies |
| `READY` | Dependencies met; queued for dispatch |
| `RUNNING` | Tool invocation in flight |
| `SUCCEEDED` | Completed successfully |
| `FAILED` | Exhausted retries |
| `SKIPPED` | Condition evaluated false |
| `ROLLED_BACK` | Rollback step executed |

---

## StageRun State Machine (legacy Job)

Maps 1:1 to pre-v0.2 job statuses:

| JobStatus (legacy) | StageRun status |
|--------------------|-----------------|
| PENDING | PENDING |
| RUNNING | RUNNING |
| COMPLETED | SUCCEEDED |
| FAILED | FAILED |
| CANCELLED | CANCELLED |

StageRun is a **denormalized view** for UI/API compatibility; authoritative
state lives in `ExecutionState.nodes`.

---

## Persistence & Concurrency

### Optimistic concurrency

Every state mutation includes `revision: int`. Writes use DynamoDB condition:

```
attribute_exists(pk) AND revision = :expected
```

On conflict: reload and retry tick (max 3).

### Distributed lock

Per execution_id, acquire lock before tick:

```python
# DynamoDB lock item: PK=LOCK#EXECUTION#{id}, TTL=now+30s
# OR Postgres advisory lock if hybrid deployment
```

Only one worker ticks a given execution at a time.

### Crash recovery

| Crash point | Recovery |
|-------------|----------|
| Mid-tool-call | Idempotency key → backend dedupes; node stays RUNNING until timeout |
| Mid-persist | Temporal retries tick; reload last committed revision |
| Mid-rollback | Rollback resumable from `rollback_progress` field |

---

## ExecutionState Model (DynamoDB)

```python
class ExecutionState(BaseModel):
    execution_id: UUID
    journey_id: str
    journey_version: int
    tenant_id: str
    status: ExecutionStatus
    revision: int

    current_stage_id: str | None
    current_stage_index: int

    graph_snapshot_id: UUID          # immutable compiled graph
    nodes: dict[UUID, NodeState]

    approval_ids: list[UUID]
    rollback_in_progress: bool

    started_at: datetime | None
    finished_at: datetime | None
    deadline_at: datetime | None

    submitted_by: str
    trace_id: str
    labels: dict[str, str]
```

### NodeState

```python
class NodeState(BaseModel):
    node_id: UUID
    step_id: str                     # DSL step id
    stage_id: str
    status: NodeStatus
    attempt: int
    last_error: str | None
    result_ref: str | None           # S3 pointer for large payloads
    started_at: datetime | None
    finished_at: datetime | None
```

---

## DynamoDB Key Design

| Entity | PK | SK |
|--------|----|----|
| Execution | `TENANT#{tid}#EXECUTION#{id}` | `STATE#v{revision}` (latest: `STATE#current`) |
| Execution index | `TENANT#{tid}#EXECUTIONS` | `STATUS#{status}#TS#{iso}` |
| StageRun (legacy) | `JOURNEY#{jid}` | `JOB#{order}#{stage}#{run_id}` |
| Lock | `LOCK#EXECUTION#{id}` | `WORKER#{worker_id}` |
| Approval | `EXECUTION#{id}` | `APPROVAL#{approval_id}` |

GSI1: `journey_id` → list executions  
GSI2: `status + started_at` → monitor dashboard

---

## Events Emitted on Transition

Prefix: `nexus.ai.executor.`

| Event | When |
|-------|------|
| `execution.submitted.v1` | Submit accepted |
| `state.transitioned.v1` | Any status change |
| `node.started.v1` | Step dispatch |
| `node.completed.v1` | Step success |
| `node.failed.v1` | Step failure |
| `approval.requested.v1` | Approval created |
| `execution.succeeded.v1` | Terminal success |
| `execution.failed.v1` | Terminal failure |

Delivered via SSE to UI; optional NATS/Kafka adapter later.

---

## UI Mapping

| UI element | State source |
|------------|--------------|
| Executions list badge | `ExecutionState.status` |
| Journey Studio progress bar | `current_stage_index / total_stages` |
| Step row icon | `NodeState.status` |
| Live log drawer | `node.*` events stream |
| Cancel button | enabled if non-terminal |
| Retry button | creates new Execution with same journey version |
