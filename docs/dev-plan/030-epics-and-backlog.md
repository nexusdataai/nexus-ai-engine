---
id: ai-engine-dev-plan-epics-backlog
title: Epics & Backlog — Nexus AI Engine
module: delivery
status: Accepted
version: "1.0.0"
owners: ["@nexus-platform/architects"]
depends_on: [ai-engine-dev-plan-master]
adrs: []
---

# Epics & Backlog — Nexus AI Engine

## Epic naming

`EPIC-<module>-<short-slug>` — referenced from sprint stories.

## Epic inventory

### Platform (E-PLAT)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-plat-repo-scaffold` | Monorepo `backend/`, `frontend/`, VERSION, CI | S1 | `002` |
| `EPIC-plat-contracts` | Pydantic contracts: Journey DSL, ExecutionGraph, ToolRequest | S1, S3 | `010`, `090` |
| `EPIC-plat-kube-operator` | Extend kube-operator for ai-engine images | S2, S10, S14 | `040` |
| `EPIC-plat-config-loader` | Settings, feature flags | S1, S5 | `001` |
| `EPIC-plat-observability` | Metrics, structured logs, health/readiness | S2, S10, S13 | `001` |
| `EPIC-plat-ci-cd` | Lint, test, build, security scan | S1, S2 | `002` |

### Journey DSL (E-JRN)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-jrn-dsl-models` | Pydantic Journey/Stage/Step models | S3 | `010` |
| `EPIC-jrn-validator` | Schema + semantic validation | S3 | `010` |
| `EPIC-jrn-compiler` | DSL → ExecutionGraph | S4 | `010`, `090` |
| `EPIC-jrn-service` | Versioned journey CRUD | S4 | `060` |
| `EPIC-jrn-migration` | Plugin YAML → DSL migration CLI | S4 | `080` |

### Executor (E-EXE)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-exe-fsm` | State machine 101-aligned | S5 | `021` |
| `EPIC-exe-manager` | ExecutionManager tick loop | S5 | `020` |
| `EPIC-exe-dispatcher` | ToolDispatcher + policy | S6, S8 | `020`, `040` |
| `EPIC-exe-retry-approval` | Retry, approval, verification engines | S5, S6 | `020` |
| `EPIC-exe-legacy-bridge` | LegacyStageAdapter for BaseStage | S6 | `080` |

### Tools (E-TOOL)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-tool-sdk` | nexus-tool-sdk: VdlClient, ConnectorClient | S7 | `040`, `041` |
| `EPIC-tool-registry` | Local ToolRegistry + DynamoDB metadata | S7, S8 | `040` |
| `EPIC-tool-packages` | Publish API, package loader | S8 | `040` |
| `EPIC-tool-o2c-migrate` | Migrate tools-o2c from nexus-backend | S8 | `040` |
| `EPIC-tool-embedded-mock` | EmbeddedToolRegistry for tests | S6 | `040` |

### Ontology integration (E-ONT)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-ont-vdl-api` | Promote `/vdl/*` on nexus-backend | S7, S8 | `041` |
| `EPIC-ont-connector-api` | Unified `/connectors/{id}/invoke` | S8 | `041` |
| `EPIC-ont-contract-tests` | SDK ↔ ontology OpenAPI tests | S8 | `041` |

### Storage (E-STORE)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-store-dynamodb-journeys` | Journey + execution tables | S9 | `050` |
| `EPIC-store-dynamodb-executions` | ExecutionState, locks, optimistic concurrency | S9 | `050` |
| `EPIC-store-s3-artifacts` | Logs, reports buckets | S9, S10 | `050` |
| `EPIC-store-migration-v01` | v0.1 jobs → executions migration | S9 | `050` |

### Workers (E-WKR)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-wkr-temporal` | RunExecutionWorkflow + activities | S10 | `030` |
| `EPIC-wkr-admission` | Concurrency limits, queue depth | S10 | `030` |
| `EPIC-wkr-helm` | Worker deployment + HPA | S10 | `001` |

### API (E-API)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-api-journeys` | Journeys REST CRUD | S4 | `060` |
| `EPIC-api-executions` | Executions lifecycle + batch | S10 | `060` |
| `EPIC-api-sse` | Execution SSE stream | S10 | `060` |
| `EPIC-api-tool-packages` | POST /tool-packages | S8 | `040`, `060` |
| `EPIC-api-mcp` | MCP execution_tool | S10 | `060` |

### UI (E-UI)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-ui-embedded` | Harden v0.1 embedded JSX UI | S2 | `UI.md` |
| `EPIC-ui-spa-scaffold` | Vite + React + TS frontend/ | S11 | `070`, `002` |
| `EPIC-ui-dashboard` | Fleet dashboard + executions list | S11 | `070` |
| `EPIC-ui-journey-studio` | DSL editor, tool picker, live graph | S12 | `070` |
| `EPIC-ui-tools-catalog` | Read-only tool package catalog | S12 | `070` |

### Decoupling & GA (E-GA)

| Epic | Description | Sprint(s) | Spec |
|---|---|---|---|
| `EPIC-ga-backend-decouple` | Copilot submits to AI Engine | S13 | `080` |
| `EPIC-ga-load-test` | 500 concurrent executions | S14 | `080` |
| `EPIC-ga-security-review` | Pen test, IAM least privilege | S14 | `001` |

### Documentation & UAT (E-DOC)

| Epic | Description | Sprint(s) | Location |
|---|---|---|---|
| `EPIC-doc-uat-alpha` | UAT v0.2.0-alpha | S2 | `delivery/010-*` |
| `EPIC-doc-uat-beta` | UAT v0.2.0-beta | S4 | `delivery/020-*` |
| `EPIC-doc-uat-rc1` | UAT v0.2.0-rc1 | S6 | `delivery/030-*` |
| `EPIC-doc-uat-rc2` | UAT v0.2.0-rc2 | S8 | `delivery/040-*` |
| `EPIC-doc-uat-v020` | UAT v0.2.0 | S10 | `delivery/050-*` |
| `EPIC-doc-uat-v030` | UAT v0.3.0 | S12 | `delivery/060-*` |
| `EPIC-doc-uat-v100` | UAT v1.0.0 | S14 | `delivery/070-*` |
| `EPIC-doc-userguide` | User guide chapters per release | S2, S4, S6, S8, S10, S12, S14 | `user-guide/` |
