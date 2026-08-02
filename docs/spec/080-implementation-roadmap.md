# 080 — Implementation Roadmap

**Version:** 0.2.0  
**Status:** Draft  

---

## Purpose

Phased plan to refactor `nexus-ai-engine` from v0.1 (extracted library +
embedded UI) to v0.2 (standalone AI Engine service with executor semantics,
distributed workers, and Journey Studio SPA).

---

## Current State (v0.1.0a1)

| Area | Status |
|------|--------|
| Library core (ports, models) | ✅ Scaffolded |
| DynamoDB adapters | ✅ Partial |
| TransformationJobExecutor | ✅ Legacy stage loop |
| Reference FastAPI server | ✅ Routes + 501 handlers |
| Embedded JSX UI | ✅ Demo/simulator |
| ExecutionManager + FSM | ❌ Not implemented |
| Journey DSL compiler | ❌ Plugin YAML only |
| Tool registry client | ❌ Not implemented |
| Temporal workers | ❌ Not implemented |
| React SPA frontend | ❌ Embedded JSX only |
| Executions API | ❌ Not implemented |

---

## Phase Overview

```text
Phase 1 ──► Specs + contracts (THIS DOCUMENT SET)
Phase 2 ──► Monorepo restructure (backend/ + frontend/)
Phase 3 ──► Journey DSL + compiler
Phase 4 ──► Execution engine core (FSM, graph, dispatcher)
Phase 5 ──► Tool registry + nexus-tool-sdk + ontology VDL/Connector integration
Phase 6 ──► DynamoDB execution storage + migration
Phase 7 ──► Distributed workers (asyncio → Temporal)
Phase 8 ──► Executions API + SSE events
Phase 9 ──► Journey Studio UI (React SPA)
Phase 10 ─► nexus-backend decoupling + production hardening
```

---

## Phase 1: Specifications (Week 1–2)

**Deliverables:**

- [x] `docs/` specification set (this directory)
- [ ] Pydantic contracts in `backend/src/nexus_ai_engine/contracts/`
- [ ] JSON Schema export (`schemas/journey-dsl-v1.json`)
- [ ] ADR: AI Engine vs nexus-sre Executor boundaries

**Exit criteria:** Spec review signed off by platform team.

---

## Phase 2: Monorepo Restructure (Week 2–3)

**Goal:** Mirror nexus-sre layout without breaking pip install.

| Task | Detail |
|------|--------|
| Create `backend/` | Move `src/nexus_ai_engine/` → `backend/src/nexus_ai_engine/` |
| Create `frontend/` | Scaffold Vite + React + TS |
| Update `pyproject.toml` | Hatchling paths, `[server]` extra unchanged |
| Update Docker | Multi-stage: frontend build + backend |
| Update Helm | Split api/ui/worker deployments |
| CI | Separate frontend lint/test job |

**Exit criteria:** `make all` passes; Docker image serves `/health` + empty SPA.

---

## Phase 3: Journey DSL + Compiler (Week 3–5)

| Task | Detail |
|------|--------|
| `contracts/journey_dsl.py` | Pydantic models from `010-journey-dsl.md` |
| `journeys/validator.py` | Schema + semantic validation |
| `journeys/compiler.py` | DSL → ExecutionGraph |
| `journeys/service.py` | Versioned CRUD |
| Migrate plugin YAML | `scripts/migrate-plugin-yaml.py` |
| Tests | Golden compile tests for 5 sample journeys |

**Exit criteria:** All `examples/journeys/*.yaml` compile to valid ExecutionGraph.

---

## Phase 4: Execution Engine Core (Week 5–8)

| Task | Detail |
|------|--------|
| `executor/manager.py` | ExecutionManager |
| `executor/engine.py` | executor_tick |
| `executor/graph.py` | Ready-node scheduler |
| `executor/retry.py` | Backoff + circuit breaker |
| `executor/approval.py` | Approval client |
| `executor/verification.py` | Post-step checks |
| `executor/rollback.py` | Rollback strategies |
| FSM tests | State transition matrix (101-aligned) |
| Legacy bridge | `LegacyStageAdapter` for BaseStage |

**Exit criteria:** Unit tests cover full FSM; mock-tool executions succeed in-process.

---

## Phase 5: Tool Registry Integration (Week 6–8)

| Task | Detail |
|------|--------|
| `tools/registry_client.py` | HttpToolRegistryClient |
| `tools/embedded_registry.py` | Test double |
| Compiler strict mode | Validate tool names |
| Backend fix | Wire PluginService → ToolRegistry |
| Contract tests | Against backend OpenAPI |
| Cache + sync worker | 5-min catalog refresh |

**Exit criteria:** O2C journey steps invoke real backend tools in staging.

---

## Phase 6: DynamoDB Execution Storage (Week 7–9)

| Task | Detail |
|------|--------|
| `ai-engine-executions-{env}` table | CloudFormation/Terraform |
| `adapters/dynamodb/execution_repo.py` | ExecutionState CRUD |
| Optimistic concurrency | revision checks |
| Lock items | TTL-based tick locks |
| Migration script | v0.1 jobs → executions |
| moto integration tests | Full repository contract suite |

**Exit criteria:** Execution survives process restart; state reloads correctly.

---

## Phase 7: Distributed Workers (Week 9–11)

| Task | Detail |
|------|--------|
| Temporal workflow | RunExecutionWorkflow |
| Activities | executor_tick, execute_node |
| `workers/temporal/worker_main.py` | Worker entrypoint |
| Helm worker deployment | HPA on queue depth |
| Admission controller | Global + per-journey limits |
| Background workers | Schedule trigger, lock cleaner |

**Exit criteria:** 50 concurrent executions across 3 worker pods in staging.

---

## Phase 8: Executions API + Events (Week 10–12)

| Task | Detail |
|------|--------|
| `/api/v1/executions` | Full CRUD + lifecycle |
| SSE stream | state + node + log events |
| Batch submit | Multiple journeys |
| Legacy jobs API | Map to executions |
| MCP execution_tool | New MCP surface |
| OpenAPI + SDK | python + typescript |

**Exit criteria:** API integration tests pass; SSE demo in CLI.

---

## Phase 9: Journey Studio UI (Week 11–14)

| Task | Detail |
|------|--------|
| Dashboard | Active executions |
| Executions monitor | Global list + filters |
| Execution detail | Graph + live logs |
| Journey Studio | DSL editor + tool picker |
| Tools catalog | Registry proxy view |
| Auth integration | Cognito JWT |
| Helm UI deployment | Separate nginx pod |

**Exit criteria:** Operator can submit, monitor, cancel journeys entirely via UI.

---

## Phase 10: Production Hardening (Week 14–16)

| Task | Detail |
|------|--------|
| nexus-backend decoupling | Backend calls AI Engine HTTP API |
| Remove duplicate journey execution from backend | CopilotEngine submits to engine |
| Load tests | 500 concurrent executions |
| Security review | Pen test, IAM least privilege |
| Observability | Grafana dashboards, alerts |
| Documentation | Operator runbook |
| Release | v0.2.0 stable |

**Exit criteria:** Production deployment with SLO: 99.9% API availability.

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Temporal ops complexity | asyncio pool for dev; managed Temporal Cloud option |
| DynamoDB hot partitions | Prefix keys with tenant; shuffle execution ids |
| Tool registry latency | Cache + async dispatch + circuit breaker |
| DSL migration breaks plugins | Legacy adapter + automated migration CLI |
| UI SSE multi-pod | Sticky sessions or Redis EventSink adapter |

---

## Team Sizing (estimate)

| Phase | Eng weeks |
|-------|-----------|
| 1–3 | 4 |
| 4–6 | 8 |
| 7–8 | 6 |
| 9–10 | 6 |
| **Total** | **~24 eng-weeks** (2 engineers ≈ 12 calendar weeks) |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Concurrent executions | 500+ |
| Submit → first step p99 | < 5s |
| Tool dispatch p99 | < 30s |
| Crash recovery | 100% resumable |
| UI live update latency | < 2s |
| Test coverage (executor) | ≥ 90% |

---

## Immediate Next Steps

1. Review and approve spec set in `docs/`
2. Create `contracts/` Pydantic models from specs
3. Begin Phase 2 monorepo restructure PR
4. Fix nexus-backend plugin → ToolRegistry wiring (parallel)
5. Prototype DSL compiler with one O2C journey
