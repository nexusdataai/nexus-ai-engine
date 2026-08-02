# Changelog

All notable changes to Nexus AI Engine are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0-rc2] — 2026-08-02

### Added

- **nexus-tool-sdk** (`packages/nexus-tool-sdk/`) — `VdlClient`, `ConnectorClient`, `ToolRuntime`, tenant header forwarding
- **Tool base + registry** — `Tool` base class, `ToolRegistry`, package loader, `POST /api/v1/tool-packages`
- **tools-o2c** (`packages/tools-o2c/`) — `O2cMatchOrderDeliveryInvoiceTool` via VDL HTTP (migrated from nexus-backend)
- **ToolDispatcher SDK path** — registry tools dispatch through `ToolRuntime`; embedded mocks as fallback
- **Strict tool validation** — journey validate/compile against published catalog (`strict_tools`, `strict_tool_validation`)
- **Ontology APIs (nexus-backend)** — `POST /api/v1/vdl/query`, `batch-query`, unified connector invoke facade
- **Contract tests** — SDK shapes vs spec 041 (`tests/contract/test_ontology_sdk_contract.py`)
- **User guide** Ch.5 — Tool packages & ontology (`docs/user-guide/05-tool-packages-ontology.md`)
- **UAT** `docs/delivery/040-v0.2.0-rc2-uat.md` — P0 7/7, P1 2/2 (local harness)

### Changed

- `InMemoryEngine` wires `execution_manager.dispatcher.registry` to `tool_registry`
- `Makefile` installs `packages/tools-o2c` editable alongside `nexus-tool-sdk`

## [0.2.0-rc1] — 2026-08-02

### Added

- **Execution FSM** (`executor/fsm.py`, `contracts/execution_state.py`) per `docs/spec/021`
- **ExecutionManager** (`executor/manager.py`) — submit, tick loop, cancel/pause/resume
- **Ready-node scheduler** (`executor/graph.py`)
- **Retry / approval / verification** stubs (`executor/retry.py`, `approval.py`, `verification.py`)
- **EmbeddedToolRegistry** with mock O2C tools (`executor/embedded_registry.py`)
- **ToolDispatcher** wired to embedded registry (`executor/tool_dispatcher.py`)
- **LegacyStageAdapter** bridge for demo processors (`executor/legacy_adapter.py`)
- **Executions REST API** (`server/routers/executions.py`): submit, list, status, nodes, graph, cancel, pause, resume
- **Integration tests**: O2C E2E, executions API, retry policy (rc1-E1–E5)
- **User guide** Ch.4 — Executions API (`docs/user-guide/04-executions-api.md`)
- **UAT** `docs/delivery/030-v0.2.0-rc1-uat.md` — P0 4/4, P1 2/2

### Changed

- `InMemoryEngine` exposes `execution_manager` and `run_execution_to_completion()`
- Node retry transition: `FAILED → retry → READY` (re-queued for dispatch)

### Not in rc1

- Temporal workflow worker, DynamoDB persistence, SSE `/stream`, remote tool registry

## [0.2.0-beta] — 2026-08-02

### Added

- **Journey DSL models** (`contracts/journey_dsl.py`) per `docs/spec/010-journey-dsl.md`
- **Semantic validator** (`journeys/validator.py`) with structured error/warning output
- **DSL compiler** (`journeys/compiler.py`) producing nexus-sre `ExecutionGraph` snapshots
- **Versioned journey store** (`journeys/service.py`) with published-version immutability
- **REST API** (`server/routers/journey_dsl_api.py`): validate, import, versions, export, clone, compile
- **Migration CLI** (`scripts/migrate-plugin-yaml.py`) for legacy plugin-journey YAML
- **Sample DSL** `examples/journeys/order-to-cash.yaml`
- **User guide** Ch.3 — Journey DSL authoring (`docs/user-guide/03-journey-dsl-authoring.md`)
- **UAT** `docs/delivery/020-v0.2.0-beta-uat.md` — P0 6/6, P1 2/2

### Changed

- `InMemoryEngine` includes `dsl_store` for DSL journey persistence (in-process)
- FastAPI app mounts `journey_dsl_api` router before legacy journey routes

### Deploy notes

- Image tag at GA cut: `nexus-ai-engine-api:0.2.0-beta-<git-sha>` (re-package after VERSION bump)
- Cluster verified: Starhub BSSMagic `ai-engine-prod` — DSL `/journeys/validate` smoke PASS

## [0.2.0-alpha] — 2026-08-02

Foundation release: contracts, monorepo layout, CI, kube-operator integration, embedded UI parity, health API, UAT α, user guide Ch.1–2.

## [0.1.0a2] — pre-release

Initial extractable library alpha; in-memory engine and reference server.
