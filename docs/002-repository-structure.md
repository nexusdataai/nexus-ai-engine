# 002 — Repository Structure

**Version:** 0.2.0  
**Status:** Draft  

---

## Purpose

Define the **target monorepo layout** for `nexus-ai-engine`, refactored to mirror
[`nexus-sre/docs/architecture/003-repository-structure.md`](../../nexus-sre/docs/architecture/003-repository-structure.md):
**domain-organized backend**, **separate frontend**, **sdk**, **helm**, **docs**.

The current repo (v0.1) is a **single Python package** with an embedded JSX UI.
The refactor evolves it into a **full service** without breaking the library
embedding modes documented in the root README.

---

## Target Top-Level Layout

```text
nexus-ai-engine/
├── README.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── docker-compose.yaml
│
├── backend/                    # Python service (NEW — migrate from src/)
│   ├── pyproject.toml
│   ├── src/nexus_ai_engine/
│   └── tests/
│
├── frontend/                   # React SPA (NEW — extract from server/static/ui)
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   └── Dockerfile
│
├── sdk/                        # Client SDKs (NEW)
│   ├── python/
│   └── typescript/
│
├── helm/                       # EXISTS — extend
│   └── nexus-ai-engine/
│
├── deploy/                     # EXISTS — admin scripts, k8s manifests
├── docs/                       # THIS directory — specifications
├── examples/                   # Sample journey DSLs
├── scripts/                    # codegen, schema export
└── .github/workflows/
```

---

## Backend Package Layout (domain-organized)

Mirrors nexus-sre `backend/src/nexus_sre/`:

```text
backend/src/nexus_ai_engine/
├── app/                        # FastAPI bootstrap, lifespan, middleware
│   └── main.py
│
├── api/                        # HTTP routers (thin)
│   ├── executions.py
│   ├── journeys.py
│   ├── stage_runs.py           # rename from jobs.py
│   ├── schedules.py
│   ├── prompts.py
│   ├── tools.py                # proxy/discovery (not implementation)
│   ├── health.py
│   └── sse.py
│
├── contracts/                  # Pydantic models = spec contracts
│   ├── journey_dsl.py
│   ├── execution_graph.py        # aligned with nexus-sre 020
│   ├── execution_state.py      # aligned with nexus-sre 021
│   ├── tool_request.py
│   └── events.py
│
├── journeys/                   # Journey domain
│   ├── service.py
│   ├── repository.py           # port
│   ├── validator.py
│   └── compiler.py             # DSL → ExecutionGraph
│
├── executor/                   # Execution domain (core)
│   ├── manager.py                # ExecutionManager
│   ├── engine.py                 # executor_tick
│   ├── graph.py                  # DAG scheduler
│   ├── approval.py
│   ├── retry.py
│   ├── verification.py
│   ├── rollback.py
│   └── tool_dispatcher.py
│
├── workers/                    # Distributed runtime
│   ├── temporal/
│   │   ├── workflows.py
│   │   ├── activities.py
│   │   └── worker_main.py
│   └── asyncio_pool.py         # lightweight local runner
│
├── tools/                      # Tool integration (NOT implementations)
│   ├── registry_client.py      # HTTP client → nexus-backend
│   ├── embedded_registry.py    # in-memory for tests
│   └── cache.py
│
├── stages/                     # Stage handlers (legacy + plugin)
│   ├── registry.py
│   ├── base_stage.py
│   ├── plugin_journey_stage.py
│   └── demo.py
│
├── schedules/                  # Cron / batch scheduling
├── prompts/                    # Prompt catalog domain
├── events/                     # SSEManager, EventSink ports
├── adapters/                   # DynamoDB, S3, in-memory
│   ├── dynamodb/
│   └── s3/
│
├── mcp/                        # MCP server tools
├── config.py
├── factory.py
└── errors.py
```

### Migration map (current → target)

| Current path | Target path | Action |
|--------------|-------------|--------|
| `src/nexus_ai_engine/server/` | `backend/.../app/` + `api/` | Split routers from bootstrap |
| `execution/transformation_job_executor.py` | `executor/` + `workers/` | Refactor into tick loop |
| `services/journey_service.py` | `journeys/service.py` | Move |
| `plugins/` | `journeys/compiler.py` + `stages/` | Merge plugin YAML into DSL compiler |
| `server/static/ui/` | `frontend/` | Extract to Vite React app |
| `testing/` | `backend/tests/` + `sdk/` fixtures | Keep harness, relocate |

---

## Frontend Layout (nexus-sre pattern)

```text
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── pages/
│   │   ├── JourneysPage.tsx          # list + search
│   │   ├── JourneyStudioPage.tsx     # DSL editor + stage sidebar
│   │   ├── ExecutionsPage.tsx        # all running journeys
│   │   ├── ExecutionDetailPage.tsx   # live graph + logs
│   │   ├── SchedulesPage.tsx
│   │   ├── PromptsPage.tsx
│   │   └── ToolsCatalogPage.tsx      # read-only registry view
│   ├── components/
│   │   ├── ExecutionGraphView.tsx      # ReactFlow — stage/step graph
│   │   ├── LiveLogDrawer.tsx
│   │   ├── StepStatusBadge.tsx
│   │   └── ApprovalPanel.tsx
│   ├── services/
│   │   └── api.ts
│   └── hooks/
│       └── useExecutionStream.ts
├── Dockerfile                      # nginx static
└── vite.config.ts
```

**Build integration:**

- **Dev:** Vite dev server proxies `/api` → FastAPI
- **Prod:** `make frontend-build` → `frontend/dist/` copied into Docker image
  OR served by separate `nexus-ai-engine-ui` pod (preferred — matches nexus-sre)

---

## SDK Layout

```text
sdk/python/nexus_ai_engine_sdk/
├── client.py           # NexusAIEngineClient
├── models.py           # Generated from contracts/
└── __init__.py

sdk/typescript/src/
├── client.ts
└── models.ts
```

Example:

```python
client = NexusAIEngineClient(base_url="...", api_key="...")
execution = await client.executions.submit(journey_id="order-to-cash", mode="full")
async for event in client.executions.stream(execution.id):
    print(event)
```

---

## Helm Chart Extensions

```text
helm/nexus-ai-engine/templates/
├── deployment-api.yaml
├── deployment-ui.yaml          # NEW
├── deployment-workers.yaml   # NEW (Temporal + stage-run workers)
├── service-api.yaml
├── service-ui.yaml
├── ingress.yaml                # /api → api, / → ui
├── hpa-workers.yaml
├── configmap.yaml
├── serviceaccount.yaml
└── temporal.yaml               # optional subchart or external ref
```

Worker deployment entrypoint:

```yaml
command: ["python", "-m", "nexus_ai_engine.workers.temporal.worker_main"]
env:
  - name: TEMPORAL_TASK_QUEUE
    value: nexus-ai-execution
```

---

## Examples Directory

```text
examples/journeys/
├── order-to-cash-monitor.yaml
├── call-processing-pipeline.yaml
├── demand-forecasting.yaml
└── supply-chain-risk.yaml
```

Each example is valid `JourneyDefinition` v1 DSL, runnable via:

```bash
nexus-ai-engine executions submit --file examples/journeys/order-to-cash-monitor.yaml
```

---

## What Stays a Library

The **`nexus_ai_engine` Python package** remains installable via pip for:

| Mode | Use case |
|------|----------|
| Embed services in-process | nexus-backend phase-10 migration |
| Mount routers in host FastAPI | Same-process HTTP |
| Testing harness | `nexus_ai_engine.testing` |

The monorepo refactor **does not** remove library embedding — it adds the
full-service layout around it.

---

## CODEOWNERS (proposed)

```
/backend/src/nexus_ai_engine/executor/   @nexus-platform/ai-engine
/backend/src/nexus_ai_engine/journeys/   @nexus-platform/ai-engine
/frontend/                             @nexus-platform/ai-engine-ui
/docs/                                 @nexus-platform/ai-engine
/sdk/                                  @nexus-platform/ai-engine
```
