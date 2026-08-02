# 030 — Distributed Worker Runtime

**Version:** 0.2.0  
**Status:** Draft  
**Aligns with:** [nexus-sre/704-distributed-worker-runtime](../../nexus-sre/docs/workflow/704-distributed-worker-runtime.md)

---

## Purpose

Define how Nexus AI Engine runs **many concurrent journey executions** across
a horizontally scaled worker fleet — the same distributed worker pattern as
nexus-sre, adapted for DynamoDB persistence and ReAct tool dispatch.

---

## Worker Tiers

### Tier 1: Temporal Execution Workers (primary)

Run `RunExecutionWorkflow` and `executor_tick` activities.

| Property | Value |
|----------|-------|
| Task queue | `nexus-ai-execution` |
| Long-poll queue | `nexus-ai-execution-longpoll` (steps with timeout > 5min) |
| Replay queue | `nexus-ai-replay` (offline replay / benchmarks) |
| Deployment | `nexus-ai-engine-workers` Deployment |
| HPA metric | `nexus_ai_temporal_activity_queue_depth` |
| Entrypoint | `python -m nexus_ai_engine.workers.temporal.worker_main` |

```yaml
# deployment-workers.yaml
replicas: 2
resources:
  requests: { cpu: 500m, memory: 1Gi }
  limits:   { cpu: 2, memory: 4Gi }
autoscaling:
  minReplicas: 2
  maxReplicas: 20
  targetQueueDepth: 10
```

### Tier 2: Asyncio Stage-Run Pool (supplementary)

Lightweight in-process scheduler for:

- Local development (`make serve`)
- Integration tests (no Temporal)
- Low-latency demo stages

```python
class AsyncioExecutionPool:
    """Runs executor_tick loops in asyncio tasks with semaphore."""
    def __init__(self, max_concurrent: int = 20): ...
    async def submit(self, execution_id: UUID) -> None: ...
```

**Not for production** when crash recovery is required — use Temporal.

### Tier 3: Background Workers (non-Temporal)

| Worker | Purpose | Schedule |
|--------|---------|----------|
| Schedule trigger | Fire cron journeys | `* * * * *` (every minute) |
| Retention | TTL old executions/logs | Daily |
| Stale lock cleaner | Release orphaned DynamoDB locks | Every 5 min |
| Metrics aggregator | Roll up step latencies | Every 1 min |
| Registry sync | Refresh tool catalog cache | Every 5 min |

Singletons use DynamoDB conditional writes for leader election (same pattern
as nexus-sre Postgres advisory locks).

---

## Concurrency Control

### Global admission

```python
class AdmissionController:
    async def admit(self, execution_id: UUID) -> bool:
        """Returns False if global max_concurrent_executions reached."""
```

Counter: DynamoDB item `COUNTER#executions#RUNNING` with atomic increment/decrement.

### Per-journey limit

Before starting execution:

```python
running = await repo.count_running(journey_id)
if running >= journey.spec.concurrency.max_parallel_runs:
    raise JourneyConcurrencyLimitError
```

Queue excess submissions as `PENDING_QUEUED` or reject with 429.

### Per-tenant fair scheduling

Optional weighted fair queue across tenants:

```text
Priority = base_priority + wait_time_bonus - tenant_running_count * penalty
```

---

## Many Journeys, Many Executions

```text
                    ┌─────────────────────────────────┐
                    │      Submission API              │
                    │  POST /executions (batch OK)     │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │     Execution Queue              │
                    │  (Temporal task queue)           │
                    └───────────────┬─────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
   Worker Pod 1               Worker Pod 2               Worker Pod N
   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
   │ Exec A tick │          │ Exec B tick │          │ Exec C tick │
   │ Exec D tick │          │ Exec E tick │          │ Exec F tick │
   └─────────────┘          └─────────────┘          └─────────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    ▼
                           DynamoDB (state)
                                    │
                                    ▼
                           nexus-backend (tools)
```

Each worker pod can tick **multiple executions** concurrently (configurable
`max_ticks_per_worker`, default 5).

---

## Isolation Options

| Profile | Use case |
|---------|----------|
| **Shared pool** | Default; all tenants on `nexus-ai-execution` |
| **Dedicated queue** | Large tenant: `nexus-ai-execution-{tenant_id}` |
| **Dedicated deployment** | Regulatory isolation; separate worker Deployment |

---

## Scaling Guidelines

From nexus-sre capacity planning (adapted):

| Metric | Target |
|--------|--------|
| Executions per worker | 5–10 concurrent ticks |
| Tool call p99 | < 30s (dominated by backend) |
| Tick duration p99 | < 2s (excluding tool wait) |
| Queue depth alert | > 100 for 5 min |

**Scale out** workers when queue depth sustained high.  
**Scale up** API pods when submission rate exceeds 500 req/s.

---

## Failure & Recovery

| Scenario | Behavior |
|----------|----------|
| Worker pod killed | Temporal reassigns activities |
| Temporal unavailable | API returns 503; executions stay PENDING |
| Stuck RUNNING node | Timeout → FAILED → retry policy |
| Orphan lock | Stale lock cleaner releases after TTL |
| Thundering herd on schedule | Admission controller + jittered start |

---

## Local Development

```bash
# Option A: asyncio pool (no Temporal)
make serve                    # MAX_CONCURRENT_JOBS=5

# Option B: Temporal dev server
docker compose up temporal
make serve-workers
```

---

## Observability

| Metric | Type |
|--------|------|
| `nexus_ai_executions_active` | Gauge |
| `nexus_ai_execution_queue_depth` | Gauge |
| `nexus_ai_worker_ticks_total` | Counter |
| `nexus_ai_tool_dispatch_duration_seconds` | Histogram |
| `nexus_ai_stage_run_duration_seconds` | Histogram |

Dashboard: Grafana "AI Engine Executions" (to be added to deploy/).

---

## Migration from TransformationJobExecutor

| Legacy | Target |
|--------|--------|
| `AsyncioJobScheduler` | Tier 2 asyncio pool |
| Single job thread per stage | Multi-execution tick loop |
| In-memory cancel set | DynamoDB status + signal |
| Direct DynamoDB writes in executor | Repository port + ExecutionManager |

Phased cutover per `080-implementation-roadmap.md`.
