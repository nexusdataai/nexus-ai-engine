# 060 — API Specification

**Version:** 0.2.0  
**Status:** Draft  
**Base path:** `/api/v1`

---

## Purpose

REST + SSE + MCP API for Nexus AI Engine as a standalone service.

Aligns with existing route parity (`docs/ROUTE_PARITY.md`) while adding
**Execution API** modeled on nexus-sre `111-execution-api.md`.

---

## Authentication

Auth is **out of scope** for the library; expected at ingress:

- Cognito JWT → `Authorization: Bearer`
- Service-to-service → mTLS + `X-Nexus-Service-Identity`

Required forwarded headers:

| Header | Required |
|--------|----------|
| `X-Nexus-Tenant-Id` | Yes (prod) |
| `X-Nexus-User-Id` | Yes (prod) |
| `X-Request-Id` | Recommended |

---

## Health & Meta

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/readiness` | DynamoDB + registry reachable |
| GET | `/version` | Build info |
| GET | `/capabilities` | Engine features, limits |

---

## Journeys API

Prefix: `/api/v1/journeys`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List journeys (filter, search, paginate) |
| POST | `/` | Create journey from DSL YAML/JSON |
| GET | `/{journey_id}` | Get journey metadata + latest version |
| PUT | `/{journey_id}` | Update metadata |
| DELETE | `/{journey_id}` | Archive journey |
| GET | `/{journey_id}/versions` | List versions |
| GET | `/{journey_id}/versions/{v}` | Get specific version DSL |
| POST | `/{journey_id}/validate` | Validate DSL without storing |
| POST | `/{journey_id}/clone` | Clone journey with new id |
| GET | `/{journey_id}/export` | Export complete YAML |
| POST | `/import` | Import journey YAML |

---

## Executions API (NEW — core)

Prefix: `/api/v1/executions`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Submit execution(s) |
| GET | `/` | List executions (status filter, journey filter) |
| GET | `/{execution_id}` | Get execution state + progress |
| GET | `/{execution_id}/graph` | Get compiled ExecutionGraph |
| GET | `/{execution_id}/nodes` | List node states |
| GET | `/{execution_id}/stream` | **SSE** live events |
| POST | `/{execution_id}/pause` | Pause |
| POST | `/{execution_id}/resume` | Resume |
| POST | `/{execution_id}/cancel` | Cancel |
| GET | `/{execution_id}/trace` | Full audit trace |
| POST | `/{execution_id}/replay` | Offline replay (admin) |
| POST | `/{execution_id}/approvals/{id}` | Submit approval decision |

### POST /executions

**Request:**

```json
{
  "journey_id": "order-to-cash-monitor",
  "journey_version": 3,
  "mode": "full",
  "stage_id": null,
  "variables": {
    "s3_prefix": "analytics/o2c/dev"
  },
  "labels": {
    "triggered_by": "schedule"
  },
  "dry_run": false
}
```

| Field | Description |
|-------|-------------|
| `mode` | `full` (all stages) \| `single_stage` \| `dry_run` |
| `stage_id` | Required if mode=single_stage |

**Response:** `202 Accepted`

```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "journey_id": "order-to-cash-monitor",
  "links": {
    "self": "/api/v1/executions/550e8400-...",
    "stream": "/api/v1/executions/550e8400-.../stream"
  }
}
```

### Batch submit

```json
{
  "submissions": [
    { "journey_id": "journey-a", "mode": "full" },
    { "journey_id": "journey-b", "mode": "single_stage", "stage_id": "main" }
  ]
}
```

Returns array of execution_ids; respects global concurrency limits.

---

## Stage Runs API (legacy Jobs)

Prefix: `/api/v1/journeys/{journey_id}/jobs`

Retained for backward compatibility; internally backed by Execution/StageRun.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs` | Start stage run (= single_stage execution) |
| GET | `/jobs` | List stage runs |
| GET | `/jobs/{job_id}` | Get run detail |
| POST | `/jobs/{job_id}/cancel` | Cancel |
| POST | `/jobs/{job_id}/retry` | Retry failed run |
| GET | `/jobs/{job_id}/stream` | SSE logs |

---

## Schedules API

Prefix: `/api/v1/journeys/{journey_id}/schedules`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/schedules` | List |
| POST | `/schedules` | Create cron schedule |
| PUT | `/schedules/{id}` | Update |
| DELETE | `/schedules/{id}` | Delete |
| POST | `/schedules/{id}/toggle` | Enable/disable |
| POST | `/schedules/{id}/run-now` | Trigger immediate execution |

---

## Prompts API

Prefix: `/api/v1/prompts`

(Unchanged from v0.1 — catalog CRUD + version history)

---

## Tools API (proxy)

Prefix: `/api/v1/tools`

Read-only proxy to nexus-backend registry (for UI Tools Catalog page):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List tools (cached) |
| GET | `/{tool_name}` | Tool metadata + JSON Schema |

Execute remains on backend — engine does not expose direct tool execute to UI
(use execution submit instead).

---

## Logs & Reports API

Prefix: `/api/v1/journeys/{journey_id}`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs/{job_id}/logs` | Step logs |
| GET | `/jobs/{job_id}/reports` | Run report |
| GET | `/executions/{execution_id}/logs` | Execution-wide logs |
| GET | `/executions/{execution_id}/reports` | Execution report |

---

## SSE Event Format

`GET /api/v1/executions/{id}/stream`

```text
event: state.transitioned
data: {"execution_id":"...","from":"RUNNING","to":"VERIFYING","ts":"..."}

event: node.completed
data: {"node_id":"...","step_id":"match_rows","duration_ms":1234}

event: log
data: {"level":"INFO","message":"Tool o2c_match... succeeded","step_id":"..."}

event: heartbeat
data: {"ts":"..."}
```

---

## MCP Tools

| Tool | Actions |
|------|---------|
| `journey_tool` | CRUD journeys, list stages, export/import |
| `execution_tool` | submit, status, cancel, list |
| `logs_and_reports_tool` | fetch logs/reports by journey/job/execution |

Schema parity with nexus-backend MCP for drop-in client migration.

---

## Error Model

```json
{
  "error": {
    "code": "JOURNEY_NOT_FOUND",
    "message": "Journey order-to-cash-monitor not found",
    "details": {}
  }
}
```

| HTTP | Codes |
|------|-------|
| 400 | VALIDATION_ERROR, INVALID_DSL |
| 404 | JOURNEY_NOT_FOUND, EXECUTION_NOT_FOUND |
| 409 | CONCURRENCY_LIMIT, REVISION_CONFLICT |
| 429 | RATE_LIMITED, ADMISSION_DENIED |
| 503 | REGISTRY_UNAVAILABLE, TEMPORAL_UNAVAILABLE |

---

## Rate Limits (recommended ingress)

| Endpoint | Limit |
|----------|-------|
| POST /executions | 100/min per tenant |
| GET /stream | 50 concurrent per tenant |
| GET /journeys | 1000/min |

---

## OpenAPI

Generated to `schemas/openapi.yaml` from FastAPI app.

SDK generation:

```bash
make sdk-generate   # python + typescript clients
```
