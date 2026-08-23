# Chapter 5 — Tool Packages & Ontology Integration

**Release:** v0.2.0-rc2 | **Sprint:** 8 | **UAT:** `docs/delivery/040-v0.2.0-rc2-uat.md`

This chapter walks through publishing a tool package to Nexus AI Engine, how tools call the ontology data plane over HTTP, and how journey validation uses the local tool catalog.

---

## Architecture recap

| Layer | Responsibility |
|-------|----------------|
| **AI Engine** | Tool packages, registry, workers, journey execution |
| **Ontology (nexus-backend)** | VDL queries, connector invokes, credentials |
| **nexus-tool-sdk** | `VdlClient`, `ConnectorClient`, `ToolRuntime` in every dispatch |

Tools never import ontology Python modules. All data access is HTTP with tenant headers forwarded from the execution context.

---

## 1. Author a tool package

Tool packages live under `packages/` (e.g. `sdk/tools-o2c`). Each tool extends `nexus_ai_engine.tools.base.tool.Tool` and implements `_dispatch(request, runtime)` using `runtime.vdl` and `runtime.connectors`.

Example: O2C three-way match (`o2c_tools.match.O2cMatchOrderDeliveryInvoiceTool`) queries `Opportunity`, `Opportunity_Line_Item`, `Delivery_Document`, and `AR_Invoice` via VDL, then computes match status locally.

---

## 2. Package manifest

Every publish requires a manifest (`sdk/examples/tool-packages/o2c/manifest.json`):

```json
{
  "apiVersion": "nexus.ai/v1",
  "kind": "ToolPackage",
  "metadata": {
    "id": "order-to-cash-tools",
    "version": "1.0.0",
    "domain": "o2c",
    "publisher": "finance-ontology"
  },
  "spec": {
    "ontology_api": {
      "vdl_base_url": "https://ontology.svc/api/v1/vdl",
      "connector_base_url": "https://ontology.svc/api/v1/connectors"
    },
    "tools": [
      {
        "tool_id": "o2c_match_order_delivery_invoice",
        "version": "1.0.0",
        "module": "o2c_tools.match:O2cMatchOrderDeliveryInvoiceTool",
        "risk_class": "read",
        "requires_approval": false
      }
    ]
  }
}
```

The `module` field must be importable in the engine worker environment (`pip install -e sdk/tools-o2c`).

---

## 3. Publish to AI Engine

```bash
curl -sf -X POST http://localhost:8001/api/v1/tool-packages \
  -H 'Content-Type: application/json' \
  -d @sdk/examples/tool-packages/o2c/manifest.json
```

Expected: `201 Created` with `tools_registered: 1`.

List registered tools:

```bash
curl -sf http://localhost:8001/api/v1/tools | jq .
curl -sf http://localhost:8001/api/v1/tools/o2c_match_order_delivery_invoice | jq .
```

Filter by domain:

```bash
curl -sf 'http://localhost:8001/api/v1/tools?domain=o2c' | jq .
```

---

## 4. Ontology VDL API

Tools call ontology over HTTP (spec `041`):

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/vdl/query` | Single virtual entity query |
| `POST /api/v1/vdl/batch-query` | Multi-entity round trip (O2C match) |
| `GET /api/v1/vdl/entities` | Entity catalog |
| `GET /api/v1/vdl/health` | Publish-time smoke |

Required headers on every call:

- `X-Nexus-Tenant-Id`
- `X-Nexus-Trace-Id`
- `X-Nexus-Execution-Id` (recommended)

Example VDL query against staging ontology:

```bash
curl -sf -X POST https://ontology/api/v1/vdl/query \
  -H 'Content-Type: application/json' \
  -H 'X-Nexus-Tenant-Id: tenant-001' \
  -d '{"virtualEntity":"Opportunity","limit":5}'
```

---

## 5. Ontology Connector API

Write tools use the unified invoke facade:

```bash
curl -sf -X POST https://ontology/api/v1/connectors/sfdc/invoke \
  -H 'Content-Type: application/json' \
  -H 'X-Nexus-Tenant-Id: tenant-001' \
  -d '{
    "action": "case.create",
    "arguments": {"Subject": "Dispute"},
    "idempotencyKey": "exec:step:1"
  }'
```

The SDK wraps this via `runtime.connectors.invoke(connector_id, action, arguments)`.

---

## 6. Journey validation (strict catalog)

After publishing tools, enable strict validation so unknown `step.tool` values fail at compile time:

```bash
curl -sf -X POST 'http://localhost:8001/api/v1/journeys/validate?strict_tools=true' \
  -H 'Content-Type: application/json' \
  -d @sdk/examples/journeys/order-to-cash.yaml
```

Compile with strict gate:

```bash
curl -sf -X POST 'http://localhost:8001/api/v1/journeys/order-to-cash-monitor/compile?strict_tool_validation=true'
```

The validator merges the **published registry catalog** with embedded rc1 mock tools (`echo`, `query_virtual_entity`, etc.).

---

## 7. Execution dispatch

When a journey runs, `ToolDispatcher`:

1. Resolves the tool from `ToolRegistry`
2. Builds `ToolRuntime` with ontology URLs from the package manifest
3. Forwards tenant/trace/execution headers to ontology
4. Falls back to `EmbeddedToolRegistry` mocks if the tool is not published

Submit an execution (rc1 API unchanged):

```bash
curl -sf -X POST http://localhost:8001/api/v1/executions/ \
  -H 'Content-Type: application/json' \
  -d '{"journey_id":"order-to-cash-monitor","tenant_id":"00000000-0000-0000-0000-000000000001"}'
```

---

## 8. Local development setup

```bash
cd nexus-ai-engine
make install-venv && source .venv/bin/activate
make serve   # port 8001
```

Install order in `Makefile`:

1. `sdk/nexus-tool-sdk`
2. `sdk/tools-o2c`
3. `nexus-ai-engine` with server extras

Run rc2 test suite:

```bash
ruff check backend/src packages tests
pytest tests/unit tests/contracts tests/contract tests/integration -q
```

---

## 9. Troubleshooting

| Symptom | Check |
|---------|-------|
| `422` on publish | Manifest schema; module path importable |
| `409` duplicate package | Bump `metadata.version` or restart in-memory engine |
| Tool not found at runtime | Publish package first; verify `GET /api/v1/tools` |
| VDL 503 | Ontology `_virtual_query_service` not initialized |
| Strict validation fails | Publish all tools referenced in journey YAML |

---

## Related docs

- Spec 040 — Tool Registry Integration
- Spec 041 — Ontology Data Plane API
- UAT — `docs/delivery/040-v0.2.0-rc2-uat.md`
- Build plan — `docs/dev-plan/build/v0.2.0-rc2-tool-platform.plan.md`
