---
id: delivery-ui-parity-alpha
title: Embedded UI Route Parity — v0.2.0-alpha
module: delivery
status: Accepted
version: "1.0.0"
owners: ["@nexus-ai-engine/platform"]
depends_on: [delivery-v0-2-0-alpha-uat]
adrs: []
---

# Embedded UI Route Parity — v0.2.0-alpha

Audit of the embedded dev UI (`/ui`) against `docs/spec/ROUTE_PARITY.md` for the
**in-memory reference server** (alpha scope).

## Mode

| Engine | Routers mounted | UI support |
|--------|-----------------|------------|
| `InMemoryEngine` (default dev) | Slim routers under `server/routers/` | Full |
| Production `Engine` | Legacy routers under `server/routers/legacy/` | Full via envelope normalizers in `app.js` |

## UI API surface (used by `app.js`)

| UI feature | HTTP route | Slim router | Status |
|------------|------------|-------------|--------|
| Journeys list | `GET /api/v1/journeys/` | `journeys.py` | PASS |
| Journey detail | `GET /api/v1/journeys/{id}` | `journeys.py` | PASS |
| Create / delete / clone | `POST/DELETE /api/v1/journeys/…` | `journeys.py` | PASS |
| Aggregate KPIs | `GET /api/v1/journeys/{id}/aggregate-report` | `reports.py` | PASS |
| Run / cancel / retry job | `POST /api/v1/journeys/{id}/jobs…` | `jobs.py` | PASS |
| Job status / logs | `GET …/status`, `GET …/logs` | `jobs.py`, `logs.py` | PASS |
| Live logs SSE | `GET …/stream` | `jobs.py` | PASS |
| Schedules CRUD + run | `/api/v1/schedules/*` | `schedules.py` | PASS |
| Prompts + audit | `/api/v1/prompts/*` | `prompts.py` | PASS |
| Stage registry enrich | `GET /api/v1/stages/registered` | `stages_registry.py` | PASS |
| Version badge | `GET /version` | `health.py` | PASS |

## Not in alpha UI (by design)

| ROUTE_PARITY entry | Reason |
|--------------------|--------|
| Copilot / journey-builder routes | Stay in nexus-backend |
| WXCC admin task-tracker routes | Stay in nexus-backend |
| `POST /batch`, `POST /execute` | Not used by embedded UI; land with DynamoDB adapter |

## Seed journeys (alpha polish)

| Journey | Capability | Steps | Demo extras |
|---------|------------|-------|-------------|
| Order-to-Cash Monitor | `order-to-cash` | 6 (incl. Workflow Actions) | Schedule every 15m |
| Supply Chain Risk | `supply-chain-risk` | 4 | Running stage + live job |
| Call Processing Pipeline | `call-processing` | 7 (2 stages) | Schedule every 30m |

Example YAML mirrors: `examples/journeys/order-to-cash-monitor.yaml`,
`examples/journeys/supply-chain-risk.yaml`.

## Verification

```bash
pytest tests/e2e/test_ui_route_parity.py tests/e2e/test_journey_ui_api.py -q
make serve   # open http://localhost:8001/ui
```
