# 090 — Nexus-SRE Executor Alignment

**Version:** 0.2.0  
**Status:** Draft  

---

## Purpose

Crosswalk between **nexus-sre Executor specifications** and **Nexus AI Engine**
implementation — showing what is reused verbatim, adapted, or intentionally
different.

---

## Spec Mapping

| nexus-sre doc | AI Engine doc | Relationship |
|---------------|---------------|--------------|
| `executor/100-executor-overview.md` | `020-execution-engine.md` | Adapted (journey input) |
| `executor/101-execution-state-machine.md` | `021-execution-state-machine.md` | **Reused** (+ PAUSED state) |
| `executor/102-executor-components.md` | `002-repository-structure.md` | Same hexagonal layout |
| `executor/103-execution-graph.md` | `010-journey-dsl.md` → compiler | Graph is output, not input |
| `executor/104-tool-dispatcher.md` | `040-tool-registry-integration.md` | Adapted (local dispatch + ontology SDK) |
| `executor/105-approval-engine.md` | `020-execution-engine.md` | **Reused** semantics |
| `executor/106-retry-engine.md` | `020-execution-engine.md` | **Reused** |
| `executor/107-verification-engine.md` | `020-execution-engine.md` | **Reused** |
| `executor/108-rollback-engine.md` | `020-execution-engine.md` | **Reused** |
| `executor/109-execution-storage.md` | `050-data-model-and-storage.md` | Adapted (DynamoDB vs Postgres) |
| `executor/110-execution-events.md` | `060-api-specification.md` (SSE) | Adapted prefix `nexus.ai.*` |
| `executor/111-execution-api.md` | `060-api-specification.md` | Adapted paths |
| `executor/112-execution-security.md` | `001-system-architecture.md` | Adapted |
| `workflow/704-distributed-worker-runtime.md` | `030-distributed-worker-runtime.md` | **Reused** pattern |
| `workflow/705-temporal-integration.md` | `020-execution-engine.md` | **Reused** workflow shell |
| `contracts/020-execution-graph.md` | `contracts/execution_graph.py` | **Shared contract** |
| `contracts/021-execution-state.md` | `contracts/execution_state.py` | **Shared contract** |
| `contracts/030-tool-request-response.md` | `contracts/tool_request.py` | **Shared contract** |
| `adr/001-executor-vs-workflow.md` | `000-ai-engine-overview.md` | Same ADR applies |

---

## Key Architectural Parallels

### ADR-001: Executor owns orchestration

| nexus-sre | AI Engine |
|-----------|-----------|
| Planner produces ExecutionGraph | DSL compiler produces ExecutionGraph |
| Temporal runs tick loop | Temporal runs tick loop |
| Postgres stores state | DynamoDB stores state |
| Infra tools (K8s, Prom) | ReAct tools (backend registry) |

### No LLM in executor tick

Both systems: **reasoning happens before submit** (Planner / Copilot).
Engine tick is deterministic.

### Distributed workers

Both systems:

- Temporal worker Deployment with HPA
- Background cron workers with leader election
- Crash recovery from persisted state

---

## Intentional Differences

| Dimension | nexus-sre | AI Engine | Rationale |
|-----------|-----------|-----------|-----------|
| **Input** | PlannerResult | JourneyDefinition DSL | Business journeys are human-authored |
| **Storage** | PostgreSQL | DynamoDB | Existing backend alignment; serverless scale |
| **Tool location** | In-process adapters | Remote HTTP registry | Tools owned by nexus-backend |
| **Event bus** | NATS JetStream | SSE (+ optional NATS) | Simpler initial deploy |
| **UI focus** | Incidents, approvals | Journeys, executions | Different operator persona |
| **Reasoning** | Planner (LangGraph) | Copilot (backend) | Out of engine scope |
| **Graph input** | From planner | From DSL compiler | DSL is the authoring surface |

---

## Shared Contract Strategy

Extract shared Pydantic models to a future **`nexus-contracts`** package
(or symlink from nexus-sre `docs/contracts/`):

```text
nexus-contracts/
├── execution_graph.py      # from nexus-sre 020
├── execution_state.py      # from nexus-sre 021
├── tool_request.py         # from nexus-sre 030
└── events.py               # shared CloudEvents types
```

Both repos depend on `nexus-contracts` to prevent drift.

**Interim:** Copy contracts into `nexus_ai_engine/contracts/` with
`schema_url` alignment and contract tests against nexus-sre JSON schemas.

---

## Workflow Docs 701–704 (Historical)

Per nexus-sre ADR-001, workflow docs 701–703 are historical redirects.
AI Engine adopts the same stance:

- **No bespoke workflow DSL** beyond Journey DSL (010)
- **No separate task scheduler** — engine handles dispatch
- **704 distributed workers** — adopted in 030
- **705 Temporal** — adopted in 020

---

## When to Use Which Executor

| Use case | Service |
|----------|---------|
| K8s incident remediation | nexus-sre Executor |
| Prometheus alert response | nexus-sre Executor |
| O2C business journey | **AI Engine** |
| Supply chain monitoring | **AI Engine** |
| Copilot-generated plan execution | **AI Engine** (submit DSL) |
| Plugin YAML journey | **AI Engine** |

Callers may use both services; no merge planned.

---

## Future Convergence (optional)

Potential shared components (not committed):

| Component | Benefit |
|-----------|---------|
| `nexus-contracts` package | Single source of truth |
| Unified observability dashboard | Fleet-wide ops view |
| Shared Temporal cluster | Reduced ops burden |
| Event federation | Cross-service audit trail |

---

## Validation Checklist

AI Engine v0.2 claims executor parity when:

- [ ] FSM transition table matches 101 (plus documented extensions)
- [ ] ExecutionGraph invariants enforced at compile time
- [ ] Retry backoff formula identical to 106
- [ ] Approval gates per 105
- [ ] Verification checks per 107
- [ ] Rollback ordering per 108
- [ ] Temporal workflow structure matches 705
- [ ] Worker HPA pattern matches 704
- [ ] Contract tests pass against nexus-sre JSON schemas

---

## References

- [nexus-sre ADR-001](../../nexus-sre/docs/adr/001-executor-vs-workflow.md)
- [nexus-sre Executor Overview](../../nexus-sre/docs/executor/100-executor-overview.md)
- [nexus-sre Execution Graph](../../nexus-sre/docs/contracts/020-execution-graph.md)
- [nexus-backend ReAct Layer](../../nexus-backend/doc/control-plane/re-act-layer.md)
