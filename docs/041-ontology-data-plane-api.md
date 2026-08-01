# 041 — Ontology Data Plane API

**Version:** 0.1.0  
**Status:** Draft  
**Related:** [040 — Tool Registry Integration](./040-tool-registry-integration.md)  
**Consumers:** Nexus AI Engine (`nexus-tool-sdk`), ontology UI, diagnostics

---

## Purpose

Define the **thin data plane API** exposed by domain ontology services
(future `nexus-ontology`; transitional implementation in `nexus-backend`).

Ontology services **do not execute ReAct tools or journeys in production**.
They provide:

1. **Virtual Data Layer (VDL) API** — query virtual entities by business name,
   routed through mapping rules to FDW, simulators, or integration feeds.
2. **Connector API** — invoke external system actions (Salesforce, Webex,
   GDrive, FDW, etc.) with credentials managed entirely within ontology.

All **compute and processing** (match logic, scoring, aggregation, transforms)
runs in **Nexus AI Engine** tool workers, which call these APIs over HTTP.

---

## Position in the Platform

```text
┌─────────────────────────────────────────────────────────────────────┐
│  Submitters: Journey Studio · Copilot UI · Schedules · SDK · MCP    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ POST /executions (DSL)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Nexus AI Engine                                                    │
│  Tool packages · Registry · Workers · FSM                           │
│       │                                                             │
│       │  nexus-tool-sdk                                             │
│       ├──► POST /api/v1/vdl/query                                   │
│       ├──► POST /api/v1/vdl/batch-query                             │
│       └──► POST /api/v1/connectors/{id}/invoke                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP (tenant-scoped)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Domain Ontology Service                                            │
│                                                                     │
│  enterprise-knowledge/  mapping rules  VirtualQueryService          │
│  connector services     PolicyEngine    credential vault            │
│                                                                     │
│  Responsibilities ONLY:                                             │
│    • Route virtual entity queries to physical sources               │
│    • Execute connector actions with stored credentials              │
│    • Enforce data-access policy per tenant                          │
│    • Serve schema / entity catalog for authoring UIs                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

1. **Credential isolation** — OAuth tokens, API keys, and connector secrets
   never leave ontology. AI Engine tools are credential-blind.
2. **Stable contracts** — VDL and Connector schemas are versioned API
   contracts; tool packages depend on them, not on Python imports.
3. **Tenant-scoped** — every request carries tenant context; PolicyEngine
   enforces entity and action permissions.
4. **Idempotent writes** — connector invokes accept `idempotency_key` for
   safe retries from AI Engine workers.
5. **Observable** — every call returns correlation IDs compatible with AI
   Engine execution tracing.
6. **Stateless API layer** — ontology API pods are horizontally scalable;
   state lives in mapping store, FDW, and credential backends.

---

## Base URL and Versioning

```
https://{ontology-service}/api/v1
```

| Path prefix | API |
|-------------|-----|
| `/vdl/*` | Virtual Data Layer |
| `/connectors/*` | External system connectors |
| `/schema/*` | Entity catalog (authoring; optional for runtime) |

Breaking changes increment `/v2`. AI Engine tool packages declare compatible
ontology API version in their manifest.

---

## Authentication and Tenancy

### Required headers (all endpoints)

| Header | Required | Purpose |
|--------|----------|---------|
| `Authorization` | Yes* | Bearer token or service mesh identity |
| `X-Nexus-Tenant-Id` | Yes | Tenant scope for policy + row filtering |
| `X-Nexus-Execution-Id` | Recommended | Correlation with AI Engine execution |
| `X-Nexus-Trace-Id` | Recommended | Distributed trace propagation |
| `X-Idempotency-Key` | Writes | Dedup connector invokes |
| `X-Nexus-User-Id` | Optional | Audit attribution (human-initiated runs) |
| `X-Nexus-Tool-Id` | Optional | Which tool initiated the call (audit) |
| `X-Nexus-Step-Id` | Optional | Journey step correlation |

\*Service-to-service calls may use mTLS + service account identity instead of
Bearer when deployed on mesh with SPIFFE/SPIRE.

### Policy enforcement

Ontology `PolicyEngine` validates on every VDL query and connector invoke:

- Tenant may access requested virtual entity
- Query filters do not violate field restrictions
- Connector action allowed for tenant + risk class
- Write rate limits per tenant / connector
- Loop detection for repeated identical queries within execution window

AI Engine forwards context; ontology **always** re-validates — never trust
caller-side policy decisions.

---

# Part 1 — Virtual Data Layer (VDL) API

## Overview

The VDL translates **virtual entity names** (e.g. `Material_Master`,
`Oracle_AR_Invoice`, `Opportunity`) to physical sources via mapping rules
defined in `enterprise-knowledge/` YAML.

Today implemented by `VirtualQueryService` in nexus-backend:

```
nexus-backend/src/services/virtual_query_service.py
nexus-backend/src/apis/control_plane_api.py  → POST /virtual/query (transitional)
```

This spec promotes VDL to a first-class ontology API at `/api/v1/vdl/*`.

---

## POST /api/v1/vdl/query

Query a single virtual entity.

### Request

```json
{
  "virtualEntity": "Opportunity",
  "fields": ["Opportunity_ID", "Total_Value", "Stage"],
  "filters": [
    {
      "field": "Opportunity_ID",
      "operator": "eq",
      "value": "OPP-001234"
    }
  ],
  "limit": 50,
  "offset": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `virtualEntity` | string | Yes | Business entity name from schema |
| `fields` | string[] | No | Subset of mapped fields; omit for all |
| `filters` | VirtualFilter[] | No | AND-combined filters |
| `limit` | int | No | Default 50, max 10000 |
| `offset` | int | No | Default 0 |

#### VirtualFilter

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | Virtual field name |
| `operator` | string | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `like`, `is_null` |
| `value` | any | Filter value; omit for `is_null` |

Aligned with `VirtualFilter` in
`nexus-backend/src/models/mapping_rule_models.py`.

### Response `200 OK`

```json
{
  "virtualEntity": "Opportunity",
  "rows": [
    {
      "Opportunity_ID": "OPP-001234",
      "Total_Value": 15000.00,
      "Stage": "Closed Won"
    }
  ],
  "metadata": {
    "sourceTable": "crm.opportunity",
    "sourceType": "fdw",
    "mappingRuleId": "mr-opp-001",
    "durationMs": 42,
    "rowCount": 1,
    "truncated": false
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `rows` | object[] | Rows with **virtual** field names |
| `metadata.sourceTable` | string | Physical source resolved by mapping |
| `metadata.sourceType` | string | `fdw`, `simulator`, `integration`, `view` |
| `metadata.durationMs` | int | Server-side query duration |
| `metadata.truncated` | bool | True if more rows exist beyond `limit` |

### Errors

| Status | Code | Description |
|--------|------|-------------|
| 400 | `invalid_request` | Malformed body |
| 404 | `entity_not_found` | Unknown virtual entity |
| 422 | `no_mapping_rule` | Entity exists but no active mapping |
| 403 | `policy_denied` | Tenant not permitted for entity/fields |
| 429 | `rate_limited` | Tenant query budget exceeded |
| 503 | `source_unavailable` | FDW / upstream unreachable (retryable) |

---

## POST /api/v1/vdl/batch-query

Execute multiple VDL queries in one HTTP round trip. Used by tools that fetch
several entities per step (e.g. O2C three-way match).

### Request

```json
{
  "queries": [
    {
      "queryId": "opp",
      "virtualEntity": "Opportunity",
      "filters": [{"field": "Opportunity_ID", "operator": "eq", "value": "OPP-001234"}],
      "limit": 1
    },
    {
      "queryId": "lines",
      "virtualEntity": "Opportunity_Line_Item",
      "filters": [{"field": "Opportunity_ID", "operator": "eq", "value": "OPP-001234"}],
      "limit": 100
    }
  ],
  "parallel": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `queries` | VdlQuery[] | Max 20 queries per batch |
| `parallel` | bool | Execute concurrently server-side (default true) |

Each `VdlQuery` uses the same schema as single query, plus optional `queryId`
for correlation in the response.

### Response `200 OK`

```json
{
  "results": [
    {
      "queryId": "opp",
      "virtualEntity": "Opportunity",
      "rows": [...],
      "metadata": {...},
      "error": null
    },
    {
      "queryId": "lines",
      "virtualEntity": "Opportunity_Line_Item",
      "rows": [...],
      "metadata": {...},
      "error": null
    }
  ],
  "durationMs": 87
}
```

Partial failure: individual results may contain `error` object while others
succeed. HTTP status remains 200 unless the entire batch is rejected.

---

## GET /api/v1/vdl/entities

List all virtual entities and mapping status.

### Response `200 OK`

```json
{
  "entities": [
    {
      "id": "Opportunity",
      "displayName": "Sales Opportunity",
      "domain": "crm",
      "mappingStatus": "active",
      "sourceType": "fdw",
      "fieldCount": 24
    },
    {
      "id": "Material_Master",
      "displayName": "Material Master",
      "domain": "supply-chain",
      "mappingStatus": "active",
      "sourceType": "simulator",
      "fieldCount": 18
    }
  ],
  "total": 45
}
```

Transitional equivalent: `GET /api/v1/control-plane/virtual/entities`.

---

## GET /api/v1/vdl/entities/{entityId}/schema

Return field definitions for authoring and compile-time validation.

### Response `200 OK`

```json
{
  "entityId": "Opportunity",
  "fields": [
    {"name": "Opportunity_ID", "type": "string", "required": true},
    {"name": "Total_Value", "type": "decimal", "required": false},
    {"name": "Stage", "type": "string", "required": false}
  ],
  "relationships": [
    {"field": "Account_ID", "targetEntity": "Account", "cardinality": "many-to-one"}
  ]
}
```

---

## GET /api/v1/vdl/entities/{entityId}/preview

Return first N rows for UI preview and publish-time smoke tests.

### Query parameters

| Param | Default | Max |
|-------|---------|-----|
| `limit` | 10 | 100 |

### Response

Same shape as `POST /vdl/query` with `limit` applied.

Transitional equivalent:
`GET /api/v1/control-plane/virtual/entities/{entity_id}/preview`.

---

## GET /api/v1/vdl/health

VDL subsystem health for publish-time validation and monitoring.

### Response `200 OK`

```json
{
  "status": "healthy",
  "mappingRulesLoaded": 45,
  "fdwConnections": {"healthy": 3, "degraded": 0},
  "latencyP99Ms": 38
}
```

---

# Part 2 — Connector API

## Overview

Connectors wrap external systems. Today nexus-backend implements per-connector
routers (GDrive, Webex, CRM/BSSMagic). This spec unifies them behind a single
**invoke** contract so AI Engine tools call one API shape for all connectors.

Ontology retains:

- OAuth flows and token refresh
- Connector-specific SDK clients
- Configuration UI and diagnostics endpoints (not used by AI Engine runtime)

---

## GET /api/v1/connectors

List available connectors and their status for the tenant.

### Response `200 OK`

```json
{
  "connectors": [
    {
      "id": "salesforce",
      "displayName": "Salesforce CRM",
      "status": "configured",
      "actions": ["create_lead", "soql_query", "update_opportunity"],
      "riskClasses": {"create_lead": "write", "soql_query": "read"}
    },
    {
      "id": "webex",
      "displayName": "Webex Calling",
      "status": "configured",
      "actions": ["search_calls", "get_recording"],
      "riskClasses": {"search_calls": "read"}
    },
    {
      "id": "gdrive",
      "displayName": "Google Drive",
      "status": "not_configured",
      "actions": ["list_files", "download_file"],
      "riskClasses": {"list_files": "read"}
    }
  ]
}
```

---

## GET /api/v1/connectors/{connectorId}/actions

Return action schemas for discovery and tool authoring.

### Response `200 OK`

```json
{
  "connectorId": "salesforce",
  "actions": [
    {
      "action": "create_lead",
      "description": "Create a CRM lead via BSSMagic",
      "riskClass": "write",
      "requiresApproval": true,
      "parameters": {
        "type": "object",
        "required": ["familyName", "companyName", "email"],
        "properties": {
          "familyName": {"type": "string"},
          "companyName": {"type": "string"},
          "email": {"type": "string", "format": "email"}
        }
      }
    },
    {
      "action": "soql_query",
      "description": "Run SOQL read query",
      "riskClass": "read",
      "parameters": {
        "type": "object",
        "required": ["soql"],
        "properties": {
          "soql": {"type": "string"}
        }
      }
    }
  ]
}
```

---

## POST /api/v1/connectors/{connectorId}/invoke

Execute a connector action. **Primary runtime endpoint** for AI Engine tools.

### Request

```json
{
  "action": "create_lead",
  "arguments": {
    "familyName": "Smith",
    "companyName": "Acme Corp",
    "email": "contact@acme.com",
    "serviceType": "General Enquiry"
  },
  "context": {
    "executionId": "exec-abc123",
    "stepId": "step-create-lead",
    "toolId": "crm_create_salesforce_lead",
    "tenantId": "tenant-001",
    "userId": "user-42"
  },
  "idempotencyKey": "exec-abc123:step-create-lead:1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | Connector action name |
| `arguments` | object | Yes | Action-specific payload |
| `context` | object | Recommended | Audit + policy context |
| `idempotencyKey` | string | Writes | Dedup key from AI Engine |
| `timeoutS` | int | No | Override default (max 300) |

### Response `200 OK`

```json
{
  "success": true,
  "result": {
    "status": "created",
    "leadId": "00Q5g00000ABC123",
    "payloadSent": {...}
  },
  "durationMs": 1240,
  "connectorId": "salesforce",
  "action": "create_lead"
}
```

### Response `200 OK` (failure encoded in body)

```json
{
  "success": false,
  "error": {
    "code": "connector_error",
    "message": "Salesforce API rate limit exceeded",
    "retryable": true
  },
  "durationMs": 890
}
```

### Errors (HTTP level)

| Status | Code | Description |
|--------|------|-------------|
| 400 | `invalid_action` | Unknown action for connector |
| 403 | `policy_denied` | Write not permitted / approval required |
| 404 | `connector_not_found` | Unknown connector id |
| 409 | `idempotency_conflict` | Same key, different payload |
| 422 | `connector_not_configured` | OAuth not set up for tenant |
| 429 | `rate_limited` | Connector or tenant limit |
| 503 | `connector_unavailable` | Upstream down (retryable) |

---

## GET /api/v1/connectors/{connectorId}/health

Per-connector health for publish-time smoke tests.

### Response `200 OK`

```json
{
  "connectorId": "salesforce",
  "status": "healthy",
  "lastTokenRefresh": "2026-08-01T10:30:00Z",
  "latencyP99Ms": 450
}
```

---

## Connector ID Registry (initial)

| `connectorId` | Source (nexus-backend today) | Example actions |
|---------------|------------------------------|-----------------|
| `salesforce` | `crm_tools.py` / BSSMagic | `create_lead`, `soql_query` |
| `webex` | `webex_connector_service.py` | `search_calls`, `get_recording` |
| `gdrive` | `gdrive_connector_service.py` | `list_files`, `download_file` |
| `fdw` | `fdw_tools.py` | `discover_tables`, `query_table` |
| `rag` | `rag_tools.py` | `hybrid_search`, `search_schema_knowledge` |

RAG/knowledge search is treated as a **read connector** when accessed via
invoke API, keeping a uniform tool SDK surface. Low-level FDW queries remain
available for tools that need physical table access outside virtual mapping.

---

# Part 3 — Schema Catalog API (authoring)

Optional for AI Engine runtime; used by ontology UI, Copilot, and Journey Studio
when browsing entities.

## GET /api/v1/schema/entities

Alias or superset of `/vdl/entities` with richer metadata from
`enterprise-knowledge/` YAML parsing.

## GET /api/v1/schema/entities/{entityId}

Full entity definition including source system mappings, business glossary, and
field descriptions.

---

# Part 4 — Migration from nexus-backend

## Transitional route mapping

| Current (nexus-backend) | Target (ontology API) |
|-------------------------|----------------------|
| `POST /api/v1/control-plane/virtual/query` | `POST /api/v1/vdl/query` |
| `GET /api/v1/control-plane/virtual/entities` | `GET /api/v1/vdl/entities` |
| `GET /api/v1/control-plane/virtual/entities/{id}/preview` | `GET /api/v1/vdl/entities/{id}/preview` |
| `POST /api/v1/control-plane/tools/{name}/execute` | **Removed** — tools run in AI Engine |
| CRM tools in-process | `POST /api/v1/connectors/salesforce/invoke` |
| Webex connector routes | `POST /api/v1/connectors/webex/invoke` |
| GDrive connector routes | `POST /api/v1/connectors/gdrive/invoke` |

During transition, ontology may expose both old and new paths with deprecation
headers on control-plane routes.

## What stays in ontology (not moved to AI Engine)

| Component | Reason |
|-----------|--------|
| `VirtualQueryService` | Mapping rule resolution, FDW routing |
| `enterprise-knowledge/` YAML | Schema source of truth |
| Connector OAuth flows | Credential management |
| Mapping rule admin UI | Domain configuration |
| Entity explorer / diagnostics | Operator tooling |
| Copilot **planning** UI | Drafts journey DSL |

## What moves to AI Engine

| Component | Reason |
|-----------|--------|
| `control_plane/tools/*.py` | Tool compute runs in workers |
| `ToolRegistry` (runtime) | Local dispatch catalog |
| `CopilotEngine.execute_plan` | Production execution |
| `AgentExecutor.run` (prod) | Optional agent in AI Engine |
| Plugin tool handlers (YAML/Python) | Loaded as tool packages |

---

# Part 5 — nexus-tool-sdk Integration

AI Engine `VdlClient` and `ConnectorClient` map directly to this API.

```python
# VdlClient → POST /api/v1/vdl/query
async def query(self, entity: str, **kwargs) -> VdlQueryResult:
    resp = await self._http.post(
        f"{self._base_url}/query",
        json={
            "virtualEntity": entity,
            "filters": kwargs.get("filters"),
            "fields": kwargs.get("fields"),
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
        },
        headers=self._forward_headers(),
    )
    return VdlQueryResult.model_validate(resp.json())

# ConnectorClient → POST /api/v1/connectors/{id}/invoke
async def invoke(self, connector_id: str, action: str, arguments: dict) -> dict:
    resp = await self._http.post(
        f"{self._base_url}/../connectors/{connector_id}/invoke",
        json={
            "action": action,
            "arguments": arguments,
            "context": self._context.to_dict(),
            "idempotencyKey": self._context.idempotency_key,
        },
        headers=self._forward_headers(),
    )
    body = resp.json()
    if not body.get("success"):
        raise ConnectorError(body["error"])
    return body["result"]
```

Tool packages declare ontology base URLs in their manifest ([040 §Tool Package](./040-tool-registry-integration.md#tool-package-publish-pipeline)).

---

# Part 6 — Testing and Publish Validation

## Ontology-side testing (tool authoring)

Domain teams test tool Python in CI against **staging ontology APIs**:

```bash
export ONTOLOGY_VDL_URL=https://ontology-staging/api/v1/vdl
export ONTOLOGY_CONNECTOR_URL=https://ontology-staging/api/v1/connectors
pytest packages/tools-supply-chain/tests/integration/
```

No in-process `VirtualQueryService` injection in tests — same HTTP path as
production.

## Publish-time smoke tests (AI Engine → ontology)

When AI Engine receives `POST /tool-packages`, optional validation:

1. `GET /api/v1/vdl/health` — VDL reachable
2. `GET /api/v1/vdl/entities` — entity catalog non-empty
3. For each connector referenced in tool descriptors:
   `GET /api/v1/connectors/{id}/health`
4. Optional sample query from manifest `smokeTest` block

---

# Part 7 — Deployment and Networking

```text
┌──────────────── K8s cluster ────────────────────────────────────────┐
│                                                                      │
│  namespace: ai-engine                                                │
│    nexus-ai-engine-workers ──────┐                                   │
│                                  │ ClusterIP / mesh                  │
│  namespace: supply-chain-ontology│                                   │
│    supply-chain-ontology-api ◄───┘                                   │
│      /api/v1/vdl/*                                                   │
│      /api/v1/connectors/*                                            │
│                                                                      │
│  NetworkPolicy: ai-engine workers → ontology:443 only                │
│  mTLS: enforced via service mesh (recommended)                       │
└──────────────────────────────────────────────────────────────────────┘
```

| Concern | Recommendation |
|---------|----------------|
| Latency | Co-locate AI Engine and ontology in same cluster |
| Timeouts | VDL default 30s; connector default 60s; tool timeout ≥ sum |
| Retries | Idempotent VDL reads: retry 503; writes: idempotency key only |
| Rate limits | Per-tenant quotas on ontology; AI Engine respects 429 |

---

# Part 8 — OpenAPI and Contract Tests

Ontology service publishes OpenAPI 3.1 at:

```
GET /api/v1/openapi.json
```

AI Engine CI runs contract tests:

- `nexus-tool-sdk` request/response shapes ↔ OpenAPI schemas
- Breaking change detection on ontology API version bumps
- Golden-file tests for VDL query/response with fixture entities

---

## Implementation Checklist (Ontology)

- [ ] Promote `/control-plane/virtual/*` → `/api/v1/vdl/*`
- [ ] Implement `POST /api/v1/vdl/batch-query`
- [ ] Unified `POST /api/v1/connectors/{id}/invoke` facade
- [ ] Map CRM tools → `salesforce` connector actions
- [ ] Map Webex routes → `webex` connector actions
- [ ] Map GDrive routes → `gdrive` connector actions
- [ ] PolicyEngine hooks on all VDL + connector endpoints
- [ ] Forward `X-Nexus-*` headers into audit log
- [ ] Deprecation headers on legacy control-plane tool execute routes
- [ ] OpenAPI spec publication
- [ ] Health endpoints for VDL and per-connector

## Implementation Checklist (AI Engine — see also 040)

- [ ] `nexus-tool-sdk` VdlClient + ConnectorClient
- [ ] Contract tests against ontology OpenAPI
- [ ] Publish-time ontology smoke validation
