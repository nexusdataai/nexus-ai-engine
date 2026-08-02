# 040 — Tool Registry Integration

**Version:** 0.3.0  
**Status:** Draft  
**Related:** [041 — Ontology Data Plane API](./041-ontology-data-plane-api.md)  
**Source of truth (legacy):** [nexus-backend control plane](../../nexus-backend/doc/control-plane/re-act-layer.md)

---

## Purpose

Define how **Nexus AI Engine** owns the **ReAct Tool Registry** and **executes
all tool logic locally** in distributed workers — while domain ontology services
(future `nexus-ontology`, starting from `nexus-backend`) expose only a **thin data
plane**: Virtual Data Layer (VDL) queries and Connector invocations over HTTP.

This spec replaces the v0.2 model where AI Engine proxied tool execution to
`nexus-backend` via `HttpToolRegistryClient`. The new model:

| Layer | Responsibility |
|-------|----------------|
| **Ontology service** | Schema, mapping rules, VDL routing, connector credentials, data APIs |
| **AI Engine** | Tool implementations, registry, dispatch, journey execution at scale |

Tools are **Python classes** loaded into AI Engine workers. They reach data
through **`nexus-tool-sdk`** clients that call ontology APIs — never through
in-process `VirtualQueryService` injection.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Domain Ontology Platform (supply-chain, O2C, …)                        │
│  future: nexus-ontology · today: nexus-backend (transitional)           │
│                                                                         │
│  enterprise-knowledge/ · mapping rules · VirtualQueryService            │
│  connector runtimes (Salesforce, Webex, GDrive, FDW)                    │
│                                                                         │
│  POST /api/v1/vdl/query          ← read path                            │
│  POST /api/v1/connectors/{id}/invoke  ← write / external path           │
│                                                                         │
│  NO production tool execution · NO production journey execution         │
└───────────────────────────────▲─────────────────────────────────────────┘
                                │ HTTP (tenant-scoped, credential-blind)
                                │
┌───────────────────────────────┴─────────────────────────────────────────┐
│  Nexus AI Engine (compute plane — domain-agnostic)                      │
│                                                                         │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────────┐  │
│  │ Tool Registry   │   │ Tool Dispatcher  │   │ Execution Manager   │  │
│  │ (local catalog) │──►│ + ToolRuntime    │──►│ (FSM, workers)      │  │
│  └────────▲────────┘   └────────┬─────────┘   └─────────────────────┘  │
│           │                     │                                       │
│  ┌────────┴────────┐   ┌────────▼─────────┐                            │
│  │ Published Tool  │   │ nexus-tool-sdk   │                            │
│  │ Packages        │   │ VdlClient        │                            │
│  │ (Python wheels) │   │ ConnectorClient  │                            │
│  └─────────────────┘   └──────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Execution flow (one DSL step)

```text
Journey step (tool_id: o2c_match_order_delivery_invoice)
    │
    ▼
ToolDispatcher.dispatch(ToolRequest)
    │
    ▼
O2cMatchTool._dispatch(request, runtime)     ← runs in AI Engine worker
    │
    ├─► runtime.vdl.query("Opportunity", filters=[...])
    ├─► runtime.vdl.query("Delivery_Document", filters=[...])
    ├─► runtime.vdl.query("Oracle_AR_Invoice", filters=[...])
    │       └── HTTP POST → ontology /api/v1/vdl/query
    │
    ├─► [match / score / aggregate — pure Python in worker]
    │
    └─► ToolResponse → persisted in execution state (DynamoDB)
```

For connector writes:

```text
runtime.connectors.invoke("salesforce", "create_lead", {...})
    └── HTTP POST → ontology /api/v1/connectors/salesforce/invoke
            └── ontology holds OAuth tokens; AI Engine never sees credentials
```

---

## Service Boundaries

| Concern | Ontology | AI Engine |
|---------|----------|-----------|
| Enterprise schema / mapping YAML | ✅ | ❌ |
| FDW / simulator routing | ✅ | ❌ |
| Connector credentials & OAuth | ✅ | ❌ |
| VDL query execution | ✅ (API) | calls API via SDK |
| Connector action execution | ✅ (API) | calls API via SDK |
| ReAct tool Python implementations | ❌ (authoring repo OK) | ✅ runs here |
| Tool registry (runtime catalog) | ❌ | ✅ authoritative |
| Tool package publish target | ❌ | ✅ |
| Journey DSL execution | ❌ | ✅ |
| Distributed concurrent workers | ❌ | ✅ |
| ReAct LLM agent loop (optional) | ❌ | ✅ (same tools) |
| Copilot journey **authoring** | ✅ UI drafts DSL | ❌ |
| Copilot journey **production run** | ❌ deprecate | ✅ |

See [041 — Ontology Data Plane API](./041-ontology-data-plane-api.md) for VDL
and Connector HTTP contracts.

---

## Tool Base Class

Aligned with nexus-sre `Tool` (`nexus_sre/tools/base/tool.py`):

```python
class Tool(ABC):
    """Every ReAct tool subclasses Tool. Runs entirely in AI Engine workers."""

    tool_id: str
    version: str

    @abstractmethod
    def descriptor(self) -> ToolDescriptor:
        """JSON Schema, risk class, capabilities — used by compiler + UI."""

    @abstractmethod
    async def _dispatch(self, request: ToolRequest, runtime: ToolRuntime) -> dict[str, Any]:
        """Execute capability. Use runtime.vdl / runtime.connectors for data access."""

    async def execute(self, request: ToolRequest, runtime: ToolRuntime) -> ToolResponse:
        """Public entry: dispatch, time, produce ToolResponse."""
        ...
```

**Rules:**

1. Tools **must not** import ontology service modules (`VirtualQueryService`, etc.).
2. Tools **must** use `ToolRuntime` for all external data and connector calls.
3. Tools **must** be idempotent when `descriptor().idempotent` is true.
4. Tools **must not** call LLMs — planning is Copilot/authoring; execution is deterministic.
5. Pure compute (transform, aggregate, format) needs no ontology calls.

### Example: migrated O2C tool

Today in nexus-backend, `o2c_tools.py` injects `VirtualQueryService` in-process.
After migration:

```python
# packages/tools-o2c/src/o2c_tools/match.py

class O2cMatchOrderDeliveryInvoiceTool(Tool):
    tool_id = "o2c_match_order_delivery_invoice"
    version = "1.0.0"

    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id=self.tool_id,
            version=self.version,
            description="Three-way match: order, delivery, invoice via VDL",
            parameters={...},  # JSON Schema
            risk_class="read",
            idempotent=True,
        )

    async def _dispatch(self, request: ToolRequest, runtime: ToolRuntime) -> dict:
        opp_id = request.arguments["opportunity_id"]

        opp = await runtime.vdl.query_one(
            "Opportunity",
            filters=[{"field": "Opportunity_ID", "operator": "eq", "value": opp_id}],
        )
        lines = await runtime.vdl.query(
            "Opportunity_Line_Item",
            filters=[{"field": "Opportunity_ID", "operator": "eq", "value": opp_id}],
            limit=100,
        )
        deliveries = await runtime.vdl.query(
            "Delivery_Document",
            filters=[{"field": "Sales_Order_ID", "operator": "eq", "value": opp_id}],
        )
        # ... compute match locally (same logic as current o2c_tools.py)
        return {"match_status": status, "opportunity_id": opp_id, ...}
```

Business logic moves unchanged; only the **data access boundary** changes from
in-process service injection to HTTP via `ToolRuntime`.

---

## nexus-tool-sdk

Shared library shipped with AI Engine and referenced by all domain tool packages.

```text
packages/nexus-tool-sdk/
├── src/nexus_tool_sdk/
│   ├── runtime.py          # ToolRuntime factory (per dispatch)
│   ├── vdl_client.py       # VdlClient, VdlQueryResult
│   ├── connector_client.py # ConnectorClient
│   ├── context.py          # ExecutionContext (tenant, user, execution_id)
│   └── errors.py             # VdlError, ConnectorError
```

### ToolRuntime

```python
@dataclass
class ToolRuntime:
    """Injected into every tool dispatch. Credential-blind."""

    vdl: VdlClient
    connectors: ConnectorClient
    context: ExecutionContext
    ontology_base_url: str      # resolved from tool package manifest
```

Created by `ToolDispatcher` per invocation, forwarding headers from the
execution submission (see [041 §Auth](./041-ontology-data-plane-api.md#authentication-and-tenancy)).

### VdlClient

```python
class VdlClient:
    def __init__(
        self,
        base_url: str,
        http: httpx.AsyncClient,
        context: ExecutionContext,
    ): ...

    async def query(
        self,
        entity: str,
        *,
        filters: list[dict] | None = None,
        fields: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> VdlQueryResult: ...

    async def query_one(self, entity: str, **kwargs) -> dict | None:
        result = await self.query(entity, limit=1, **kwargs)
        return result.rows[0] if result.rows else None

    async def batch_query(self, requests: list[VdlQuerySpec]) -> list[VdlQueryResult]:
        """POST /api/v1/vdl/batch-query — reduces round trips for multi-entity tools."""
```

### ConnectorClient

```python
class ConnectorClient:
    async def invoke(
        self,
        connector_id: str,
        action: str,
        arguments: dict,
    ) -> dict:
        """POST /api/v1/connectors/{connector_id}/invoke"""
```

---

## Tool Registry (AI Engine — local)

The runtime catalog lives **inside AI Engine**, not in ontology.

```python
class ToolRegistry:
    """In-process registry loaded from published tool packages."""

    def register(self, tool: Tool) -> None: ...
    def get(self, tool_id: str, version: str | None = None) -> Tool: ...
    def list_tools(self, domain: str | None = None) -> list[ToolDescriptor]: ...
    def load_package(self, package: ToolPackageManifest) -> None: ...
```

### Storage

| Store | Contents |
|-------|----------|
| DynamoDB `ai-engine-tools-{env}` | Package metadata, tool descriptors, publish provenance |
| Worker filesystem / container image | Python wheels or plugin artifacts |
| S3 `ai-engine-tool-packages-{env}` | Published package blobs (optional) |

Tool **code** is not stored as blobs in DynamoDB — only metadata and manifest.
Code ships as deployment artifacts (wheel, plugin zip) loaded at worker startup
or on publish.

---

## Tool Package Publish Pipeline

Domain teams author tools in ontology-adjacent repos (or monorepo packages),
test against staging ontology VDL/Connector APIs, then publish to AI Engine.

### Package manifest

```yaml
apiVersion: nexus.ai/v1
kind: ToolPackage
metadata:
  id: supply-chain-tools
  version: 2.1.0
  domain: supply-chain
  publisher: supply-chain-ontology
spec:
  ontology_api:
    vdl_base_url: https://supply-chain-ontology.svc/api/v1/vdl
    connector_base_url: https://supply-chain-ontology.svc/api/v1/connectors
  tools:
    - tool_id: sc_match_shipment_invoice
      version: "1.0.0"
      module: supply_chain_tools.match:ScMatchShipmentInvoiceTool
      risk_class: read
      requires_approval: false
    - tool_id: sc_score_supplier_risk
      version: "1.0.0"
      module: supply_chain_tools.risk:ScScoreSupplierRiskTool
      risk_class: read
  provenance:
    test_suite: supply-chain-tools-v2.1.0
    test_report_uri: s3://nexus-ci/reports/supply-chain-tools-2.1.0.json
    git_sha: abc123def456
```

### Lifecycle

```text
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Author  │ → │   Test   │ → │  Stage   │ → │ Publish  │ → │  Run in  │
│  Python  │   │ vs VDL   │   │  package │   │ to Engine│   │ AI Engine│
│  tools   │   │ + Conn.  │   │  + wheel │   │          │   │ journeys │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
     │              │                                              │
     │              └── pytest + staging ontology APIs              │
     │                  (same HTTP contract as production)          │
     └──────────────────────────────────────────────────────────────┘
```

### AI Engine publish API

```
POST /api/v1/tool-packages
Content-Type: multipart/form-data | application/json

Body:
  manifest: ToolPackageManifest (YAML/JSON)
  artifact: wheel | zip (optional if pre-baked in worker image)
```

**Publish validation steps:**

1. Parse and validate manifest schema.
2. Verify each `tool_id` + `module` resolves to a loadable `Tool` subclass.
3. Validate `descriptor()` JSON Schema for each tool.
4. Optional smoke test: `GET {ontology}/health`, sample VDL query if configured.
5. Store metadata in DynamoDB; load tools into worker registry.
6. Return `{ package_id, version, tools_registered: N }`.

```
GET  /api/v1/tools                    # merged catalog (all domains)
GET  /api/v1/tools/{tool_id}          # descriptor + package provenance
DELETE /api/v1/tool-packages/{id}/{version}  # deactivate (soft)
```

---

## Tool Dispatcher

```python
class ToolDispatcher:
    def __init__(
        self,
        registry: ToolRegistry,
        http: httpx.AsyncClient,
        policy_engine: ExecutionPolicyEngine,  # AI Engine side
    ): ...

    async def dispatch(self, request: ToolRequest) -> ToolResponse:
        tool = self._registry.get(request.tool_id)
        self._policy_engine.validate(request, tool.descriptor())

        package = self._registry.get_package_for_tool(request.tool_id)
        runtime = ToolRuntime(
            vdl=VdlClient(package.ontology_api.vdl_base_url, self._http, request.context),
            connectors=ConnectorClient(package.ontology_api.connector_base_url, ...),
            context=request.context,
            ontology_base_url=package.ontology_api.base,
        )
        return await tool.execute(request, runtime)
```

Policy is split:

| Policy | Where enforced |
|--------|----------------|
| Journey step budget, approval gates, retry | AI Engine `ExecutionPolicyEngine` |
| VDL entity access, connector write limits | Ontology `PolicyEngine` (on API calls) |

AI Engine **does not bypass** ontology policy — every VDL/connector call goes
through ontology HTTP APIs with forwarded tenant context.

---

## ToolRequest / ToolResponse Contract

Aligned with nexus-sre `030-tool-request-response.md`:

```python
class ToolRequest(BaseModel):
    tool_id: str
    capability: str = "nexus-ai"
    arguments: dict
    idempotency_key: str
    mode: ToolMode                    # read | write | destructive
    timeout_s: int = 300
    tenant_id: str
    trace_id: str
    context: ExecutionContext         # execution_id, step_id, journey_id, user_id
```

```python
class ToolResponse(BaseModel):
    success: bool
    result: dict | None
    error_code: str | None
    error_message: str | None
    retryable: bool = False
    duration_ms: int
    vdl_calls: int = 0                # observability
    connector_calls: int = 0
```

### DSL step → ToolRequest mapping

| DSL field | ToolRequest field |
|-----------|-------------------|
| `step.tool` | `tool_id` |
| `step.params` (resolved) | `arguments` |
| `step.risk_class` | `mode` |
| `step.timeout_s` | `timeout_s` |
| execution context | `context` |
| `{execution_id}:{node_id}:{attempt}` | `idempotency_key` |

---

## Validation

### Compile time (`strict_tool_validation: true`)

1. Compiler loads tool catalog from local registry (cached from DynamoDB).
2. Each `step.tool` must exist in catalog.
3. Required parameters checked against JSON Schema (static subset).
4. Unknown tools → compile error with suggestion list from catalog.

When `false` (dev mode): warn only; runtime failure if tool missing.

### Runtime (AI Engine)

- Unknown tool → node `FAILED`, non-retryable.
- Tool timeout → retry per step policy.
- Ontology VDL 403 → policy violation, non-retryable.
- Ontology 503 → retryable with backoff.
- Connector invoke failure → per tool `retryable` flag.

---

## Multi-Domain Support

One AI Engine cluster serves tools from **multiple ontology domains**:

```text
Tool Catalog (AI Engine)
├── supply-chain-tools@2.1.0     → ontology: supply-chain-ontology
├── order-to-cash-tools@1.4.0    → ontology: finance-ontology
└── generic-compute@1.0.0        → ontology: none (pure local tools)
```

Each package manifest declares its `ontology_api` base URLs. Journeys reference
tools by `tool_id`; the dispatcher resolves the owning package and ontology
endpoint at runtime.

---

## ReAct Agent vs Deterministic DSL

Both modes use **identical tool implementations** in AI Engine:

| Mode | Trigger | Tool selection |
|------|---------|----------------|
| **Deterministic DSL** | Journey submission | Fixed `step.tool` from compiled graph |
| **ReAct agent** (optional) | `POST /agent/run` | LLM picks from catalog via function calling |

Ontology does **not** run `AgentExecutor` or `CopilotEngine.execute_plan` in
production. Copilot in ontology UI may **draft journey DSL** and submit
executions to AI Engine.

---

## Testing Strategy

### Unit tests (AI Engine / tool packages)

Mock `VdlClient` and `ConnectorClient` — no network.

```python
@pytest.fixture
def mock_runtime():
    return ToolRuntime(
        vdl=MockVdlClient(responses={"Opportunity": [...]}),
        connectors=MockConnectorClient(),
        context=ExecutionContext(tenant_id="test"),
    )
```

### Integration tests (tool packages + staging ontology)

Point SDK at staging ontology — **same HTTP contract as production**:

```bash
ONTOLOGY_STAGING_URL=https://ontology-staging.svc \
  pytest packages/tools-o2c/tests/integration/
```

### Contract tests

- AI Engine publish API ↔ tool package manifest schema.
- `nexus-tool-sdk` ↔ ontology OpenAPI ([041](./041-ontology-data-plane-api.md)).

### Embedded registry (offline / JourneyYAMLRunner)

```python
class EmbeddedToolRegistry(ToolRegistry):
    """In-memory registry for unit tests and local harness."""
    def register(self, tool: Tool) -> None: ...
```

Register mock tools or real tool classes with mock `ToolRuntime`.

---

## Migration from nexus-backend (transitional)

| Today (nexus-backend) | Target |
|-----------------------|--------|
| `register_*_tools(registry, vq_service)` in `control_plane_api.py` | Tool packages in AI Engine; `VdlClient` replaces injection |
| `src/services/control_plane/tools/*.py` | `packages/tools-{domain}/` in AI Engine monorepo |
| `CopilotEngine.execute_plan()` production path | Dev preview only; prod → `POST /executions` on AI Engine |
| `AgentExecutor.run()` in backend | Optional `AgentExecutor` in AI Engine |
| Plugin YAML tools via `PluginService.activate()` | YAML tools loaded in AI Engine; VDL steps use SDK |
| `POST /control-plane/tools/{name}/execute` | **Deprecated** for AI Engine dispatch |
| `POST /control-plane/virtual/query` | Promoted to `POST /api/v1/vdl/query` on ontology |

### Transitional dual-run period

During migration, nexus-backend may continue registering tools for Copilot
preview. Production journey submissions must target AI Engine only. Feature flag
`AI_ENGINE_EXECUTION_ENABLED` gates the cutover per tenant.

---

## Repository Layout

```text
nexus-ai-engine/
├── packages/
│   ├── nexus-tool-sdk/           # VdlClient, ConnectorClient, Tool base
│   ├── tools-o2c/                # migrated from nexus-backend
│   ├── tools-supply-chain/
│   └── tools-generic/            # compute, transform (no ontology)
├── backend/src/nexus_ai_engine/
│   ├── registry/                 # ToolRegistry, package loader
│   ├── executor/tools/           # ToolDispatcher, ToolRuntime factory
│   └── api/tool_packages.py      # publish API
└── docs/
    ├── 040-tool-registry-integration.md   # this document
    └── 041-ontology-data-plane-api.md

supply-chain-ontology/            # future thin data plane
├── enterprise-knowledge/
├── src/vdl/
├── src/connectors/
└── src/api/                      # vdl_api.py, connector_api.py
```

Domain teams may maintain tool packages in separate repos; publish wheels to
AI Engine via CI.

---

## Performance

Multi-entity tools (e.g. O2C three-way match) issue several VDL queries per
step. Mitigations:

| Technique | Description |
|-----------|-------------|
| Co-location | AI Engine + ontology in same cluster/VPC |
| Batch VDL API | `POST /vdl/batch-query` — see [041](./041-ontology-data-plane-api.md) |
| Connection pooling | Shared `httpx.AsyncClient` per worker process |
| Execution-scoped cache | Read cache keyed by `(execution_id, entity, filters_hash)` |
| Prefetch hints | DSL `prefetch_entities` on steps (future compiler optimization) |

Target: p99 VDL latency < 50 ms in-cluster; tool step budget accounts for
N × VDL calls in timeout configuration.

---

## Security

- mTLS or service mesh between AI Engine workers and ontology APIs.
- **No connector credentials in AI Engine** — tools are credential-blind.
- Write/destructive tools require approval nodes or AI Engine policy gates.
- Ontology enforces entity-level and connector-action policy on every API call.
- Audit log: `tool_id`, arguments hash, result hash, `vdl_calls`, `connector_calls`.
- Published packages signed; manifest includes `git_sha` and test report URI.

---

## MCP Exposure (AI Engine)

AI Engine MCP tools manage journeys, executions, and tool packages — not
individual ontology data APIs:

| MCP Tool | Purpose |
|----------|---------|
| `journey_tool` | CRUD journeys |
| `execution_tool` | Submit/monitor executions |
| `tool_package_tool` | Publish/list tool packages |
| `logs_and_reports_tool` | Fetch artifacts |

VDL and Connector APIs are ontology MCP/API concerns ([041](./041-ontology-data-plane-api.md)).

---

## Error Handling

| Condition | AI Engine action |
|-----------|------------------|
| Tool dispatch success | Node `SUCCEEDED` |
| Unknown tool_id | Node `FAILED`, non-retryable |
| Tool `ToolExecutionError(retryable=False)` | Node `FAILED`, non-retryable |
| Tool timeout | Retry per step policy |
| Ontology VDL 403 | Node `FAILED`, policy violation |
| Ontology VDL 503 / network | Retry with backoff |
| Connector 429 | Retry with backoff |
| Package load failure at publish | Reject publish, keep prior version |

---

## Implementation Checklist

- [ ] `packages/nexus-tool-sdk` — VdlClient, ConnectorClient, ToolRuntime
- [ ] `Tool` base class aligned with nexus-sre contract
- [ ] `ToolRegistry` + DynamoDB metadata store
- [ ] `ToolDispatcher` with ExecutionPolicyEngine
- [ ] `POST /api/v1/tool-packages` publish API
- [ ] Package loader (wheel/zip) in worker startup
- [ ] Migrate `tools-o2c` from nexus-backend as reference package
- [ ] Compiler strict tool validation against local catalog
- [ ] Integration test harness pointing at staging ontology
- [ ] Deprecate `HttpToolRegistryClient` (v0.2 remote-execute model)
- [ ] Ontology: promote VDL + unified Connector API per [041](./041-ontology-data-plane-api.md)
- [ ] Remove production `CopilotEngine.execute_plan` path from nexus-backend
