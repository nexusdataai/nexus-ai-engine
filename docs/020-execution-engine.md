# 020 — Execution Engine

**Version:** 0.2.0  
**Status:** Draft  
**Aligns with:** [nexus-sre/100-executor-overview](../../nexus-sre/docs/executor/100-executor-overview.md)

---

## Purpose

Define the **AI Engine Executor** — the deterministic orchestration core that
transforms a compiled `ExecutionGraph` into verified tool invocations.

This is a **port** of nexus-sre Executor semantics to the journey domain,
replacing `TransformationJobExecutor`'s ad-hoc stage loop.

---

## Non-Responsibilities

Same as nexus-sre Executor:

- No LLM calls
- No plan generation
- No tool implementation
- No learning / reward computation

---

## Component Map

| nexus-sre component | AI Engine component | Notes |
|---------------------|---------------------|-------|
| `ExecutionManager` | `executor/manager.py` | Orchestrates tick loop |
| `ExecutionGraph` scheduler | `executor/graph.py` | Ready-node selection |
| `ToolDispatcher` | `executor/tool_dispatcher.py` | Calls nexus-backend registry |
| `RetryEngine` | `executor/retry.py` | Same backoff semantics |
| `ApprovalEngine` (client) | `executor/approval.py` | Inline + plan-level |
| `VerificationEngine` | `executor/verification.py` | Post-step checks |
| `RollbackEngine` | `executor/rollback.py` | On failure strategies |
| `ExecutionStorage` | `adapters/dynamodb/execution_repo.py` | DynamoDB not Postgres |

---

## Execution Manager

```python
class ExecutionManager:
    async def submit(self, request: SubmitExecutionRequest) -> ExecutionState: ...
    async def tick(self, execution_id: UUID) -> TickOutcome: ...
    async def pause(self, execution_id: UUID) -> None: ...
    async def resume(self, execution_id: UUID) -> None: ...
    async def cancel(self, execution_id: UUID) -> None: ...
```

### Submit flow

1. Load `JourneyDefinition` by id/version
2. Validate DSL (schema + semantic)
3. `graph = JourneyCompiler().compile(journey)`
4. Create `ExecutionState(status=PENDING, graph_snapshot=graph)`
5. Persist to DynamoDB
6. Enqueue Temporal workflow `RunExecutionWorkflow(execution_id)`
7. Return execution_id

### Tick flow (one iteration)

Adapted from nexus-sre `101-execution-state-machine.md`:

```text
1. Acquire DynamoDB conditional lock (execution_id, expected_revision)
2. Load ExecutionState + graph snapshot
3. If terminal → return DONE
4. If AWAITING_APPROVAL → check approval status; transition if resolved
5. Select ready nodes (deps satisfied, parallelism budget)
6. For each ready node:
     a. APPROVAL → create approval record, wait
     b. TOOL_CALL → ToolDispatcher.dispatch
     c. VERIFY → VerificationEngine.run
     d. NOOP → mark succeeded
7. Apply retry policy on failures
8. If failure policy triggers → ROLLBACK_PENDING
9. Persist state (revision++)
10. Emit CloudEvents / SSE
11. Return CONTINUE | DONE | WAIT_APPROVAL
```

---

## Graph Scheduler

Ready node selection:

```python
def ready_nodes(state: ExecutionState, graph: ExecutionGraph) -> list[UUID]:
    """Nodes where all depends_on succeeded and parallelism budget allows."""
```

Constraints:

- `graph.max_parallelism` — global cap per tick
- `journey.spec.concurrency.max_parallel_steps` — journey cap
- Running nodes count toward budget

Stage boundaries: when all nodes in current stage complete, advance `current_stage_index`
or mark execution `SUCCEEDED` if last stage.

---

## Tool Dispatcher

**Sole gateway** to ReAct tools. Mirrors nexus-sre `104-tool-dispatcher.md`.

```python
class ToolDispatcher:
    def __init__(self, registry: ToolRegistryClient, breaker: CircuitBreaker): ...

    async def dispatch(self, request: ToolRequest) -> ToolResponse:
        # 1. Resolve tool metadata (cached)
        # 2. Build idempotency_key = f"{execution_id}:{node_id}:{attempt}"
        # 3. HTTP POST to nexus-backend
        # 4. Map response → NodeOutcome
        # 5. Record latency metric
```

### ToolRequest mapping (from DSL step)

```python
ToolRequest(
    tool_id=step.tool,
    capability="nexus-ai",           # or journey metadata label
    arguments=resolved_params,
    idempotency_key=f"{execution_id}:{step_id}:{attempt}",
    mode=ToolMode.from_risk(step.risk_class),
    credentials=[],                   # secret refs resolved by backend
    context={
        "tenant_id": tenant_id,
        "execution_id": str(execution_id),
        "journey_id": journey_id,
        "stage_id": stage_id,
        "step_id": step_id,
    },
)
```

---

## Retry Engine

Identical semantics to nexus-sre `106-retry-engine.md`:

- Per-node `RetryPolicy` from DSL defaults/overrides
- Non-retryable: `POLICY_VIOLATION`, `VALIDATION_ERROR`, `APPROVAL_REJECTED`
- Circuit breaker per tool_id (persisted in DynamoDB `TOOL_BREAKER#{tool_id}`)
- Jittered exponential backoff

---

## Approval Engine

Client-only (approvals stored in DynamoDB):

| Mode | Trigger |
|------|---------|
| Plan-level | `journey.spec.requires_approval: true` before any tool |
| Step-level | `step.requires_approval: true` |
| Risk-derived | `risk_class: destructive` auto-inserts approval node |

API: `POST /api/v1/executions/{id}/approvals/{approval_id}`

UI: Approval panel in Journey Studio (Executions detail page).

---

## Verification Engine

Post-step checks from DSL `verification:` blocks:

| Check type | Evaluator |
|------------|-----------|
| Expression | CEL/JMESPath on `$result` |
| Tool call | Nested tool invocation (read-only) |
| HTTP get | External probe |

`on_failure: warn` → log and continue; `abort` → fail stage.

---

## Rollback Engine

When stage fails with `on_failure: rollback`:

1. Transition `ROLLBACK_PENDING → ROLLING_BACK`
2. Execute `rollback.steps` in reverse dependency order
3. Terminal state `FAILED` (even if rollback succeeds)

---

## Temporal Integration

Thin workflow per nexus-sre `705-temporal-integration.md`:

```python
@workflow.defn
class RunExecutionWorkflow:
    @workflow.run
    async def run(self, execution_id: str) -> None:
        while True:
            outcome = await workflow.execute_activity(
                executor_tick,
                execution_id,
                start_to_close_timeout=timedelta(minutes=5),
            )
            if outcome.done:
                return
            if outcome.wait_until:
                await workflow.sleep(outcome.wait_until)
            else:
                await workflow.sleep(timedelta(seconds=1))
```

Task queue: `nexus-ai-execution`

Activities:

- `executor_tick(execution_id) → TickOutcome`
- `execute_node(execution_id, node_id) → NodeOutcome` (optional long-running isolation)

Signals: `apply_approval`, `cancel`, `pause`, `resume`

---

## Legacy Stage Handler Bridge

During migration, **imperative stages** (`BaseStage` subclasses like `order_to_cash`)
coexist with DSL steps:

```python
class LegacyStageAdapter:
    """Wraps BaseStage.process() as a single TOOL_CALL node."""
```

Registry in `stages/registry.py` maps `stage_id` → Python class for journeys
not yet migrated to pure DSL.

Target: all production journeys use DSL; legacy adapter removed in v1.0.

---

## Configuration

```python
@dataclass
class ExecutorConfig:
    max_concurrent_executions: int = 50
    max_nodes_per_tick: int = 10
    default_tick_interval_s: float = 1.0
    tool_registry_url: str = "http://nexus-backend:8000"
    tool_registry_timeout_s: float = 30.0
    strict_tool_validation: bool = True
    enable_verification: bool = True
    enable_rollback: bool = True
```

---

## Testing Strategy

| Tier | Focus |
|------|-------|
| Unit | Graph scheduler, compiler, retry math |
| Contract | ToolRequest/Response round-trip vs backend |
| Integration | moto DynamoDB + mock registry |
| Replay | Golden execution traces |
| Journey | YAML examples end-to-end |

Harness: existing `nexus_ai_engine.testing.JourneyYAMLRunner` extended for Execution API.
