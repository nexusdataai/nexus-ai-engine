# Route parity inventory

This document is the **source of truth** for the reference server's HTTP surface during the
nexus-backend → nexus-ai-engine extraction. Each phase (2–9 of the master extraction plan)
activates the routes tied to the services it ports. No route in this library may simplify,
shortcut, or diverge from the nexus-backend source without an explicit, documented reason.

> Every fix, optimization, retry, caching behavior, decimal conversion, error-path nuance,
> and edge case in the source must be preserved **verbatim** during the phase port. The e2e
> tests migrated from nexus-backend in the same phase PR are the safety net.

## How to port a route

1. Open the referenced `file:lineStart-lineEnd` range in the nexus-backend source.
2. Translate the function body to use library services (`JourneyService`, `PromptsService`,
   `LogsAndReportsService`) instead of nexus-backend's direct DynamoDB/S3 calls or imports.
3. Keep every branch, guard, and early-return. If the source has a comment starting with
   `# fix`, `# ensure`, `# workaround`, `# optimization`, `# handle`, transport it verbatim.
4. Stamp the phase PR description with the commit SHA of nexus-backend's `dev` branch you
   ported from, so drift is detectable later via `git log <sha>..origin/dev -- <source>`.
5. Migrate the corresponding nexus-backend test(s) to `tests/e2e/` in the same PR.

## Phase activation (from the master plan)

| Phase | Routes activated | Source services moved |
|-------|------------------|-----------------------|
| 5 | Prompts (all)                          | `PromptsService` |
| 6 | Logs, Reports, aggregate-report        | `LogsAndReportsService` |
| 7 | Jobs (start/get/status/cancel/retry/logs/reports/errors/stream/ws), job admin | `TransformationJobExecutor`, `SSEManager` |
| 9 | Journeys (CRUD, stages, clone, batch, execute, metrics)                       | `JourneyService`, `AsyncioJobScheduler` |
| out-of-scope / nexus-backend only | Copilot journey + journey builder | Stays in nexus-backend (depends on copilot engine, not journey engine) |

Until the activating phase lands, the library's router returns **501 Not Implemented** on
each endpoint. CI does not treat 501 as a failure for these routes.

---

## Journeys API

Source: [nexus-backend/src/apis/journey_api.py](../../nexus-backend/src/apis/journey_api.py)
Library target: `src/nexus_ai_engine/server/routers/journeys.py` + `src/nexus_ai_engine/server/routers/jobs.py`

### Journey CRUD

| Method | Path | Source lines | Library phase |
|--------|------|-------------|---------------|
| POST   | `/`                           | 156-202  | 9 |
| GET    | `/{journey_id}`               | 203-252  | 9 |
| GET    | `/{journey_id}/status`        | 253-306  | 9 |
| GET    | `/`                           | 307-382  | 9 |
| DELETE | `/{journey_id}`               | 383-417  | 9 |
| POST   | `/batch`                      | 418-487  | 9 |
| POST   | `/{journey_id}/execute`       | 488-538  | 9 |
| GET    | `/{journey_id}/metrics`       | 539-588  | 9 |
| POST   | `/{journey_id}/clone`         | 589-643  | 9 |

### Stages

| Method | Path | Source lines | Library phase |
|--------|------|-------------|---------------|
| GET    | `/{journey_id}/stages`                     | 644-697  | 9 |
| POST   | `/{journey_id}/stages`                     | 698-765  | 9 |
| PUT    | `/{journey_id}/stages/{stage_id}`          | 766-827  | 9 |
| DELETE | `/{journey_id}/stages/{stage_id}`          | 828-865  | 9 |

### Jobs

| Method | Path | Source lines | Library phase |
|--------|------|-------------|---------------|
| POST   | `/{journey_id}/jobs`                       | 866-943   | 7 |
| GET    | `/{journey_id}/jobs`                       | 944-1025  | 7 |
| GET    | `/{journey_id}/jobs/{job_id}`              | 1026-1093 | 7 |
| GET    | `/{journey_id}/jobs/{job_id}/status`       | 1094-1230 | 7 |
| POST   | `/{journey_id}/jobs/{job_id}/cancel`       | 1231-1283 | 7 |
| POST   | `/{journey_id}/jobs/{job_id}/retry`        | 1284-1353 | 7 |

### Logs, reports, errors, streams

| Method | Path | Source lines | Library phase |
|--------|------|-------------|---------------|
| GET    | `/{journey_id}/jobs/{job_id}/logs`              | 1354-1456 | 6 |
| GET    | `/{journey_id}/aggregate-report`                | 1457-1481 | 6 |
| GET    | `/{journey_id}/jobs/{job_id}/reports`           | 1482-1531 | 6 |
| POST   | `/{journey_id}/jobs/{job_id}/reports`           | 1532-1583 | 6 |
| GET    | `/{journey_id}/jobs/{job_id}/logs/search`       | 1584-1632 | 6 |
| GET    | `/{journey_id}/jobs/{job_id}/errors`            | 1633-1678 | 6 |
| WS     | `/{journey_id}/jobs/{job_id}/ws`                | 1679-1788 | 7 |
| GET    | `/{journey_id}/jobs/{job_id}/stream`            | 1789-1845 | 7 |
| GET    | `/{journey_id}/jobs/{job_id}/stream/status`     | 1846-1864 | 7 |

### Admin (task tracker — WXCC-specific)

Not migrating. These admin routes target WXCC-specific task deduplication state that lives
in nexus-backend. They stay in nexus-backend.

| Method | Path | Source lines | Disposition |
|--------|------|-------------|-------------|
| POST   | `/admin/reset-task-tracker`        | 1871-1944 | Stays in nexus-backend |
| GET    | `/admin/task-tracker`              | 1945-1996 | Stays in nexus-backend |
| POST   | `/admin/task-tracker/delete`       | 1997-end  | Stays in nexus-backend |

---

## Prompts API

Source: [nexus-backend/src/apis/prompts_api.py](../../nexus-backend/src/apis/prompts_api.py)
Library target: `src/nexus_ai_engine/server/routers/prompts.py`

| Method | Path | Source lines | Library phase |
|--------|------|-------------|---------------|
| GET    | `""` (list)                  | 49-75   | 5 |
| GET    | `/types`                     | 76-93   | 5 |
| GET    | `/{prompt_id}`               | 94-128  | 5 |
| PUT    | `/{prompt_id}`               | 129-173 | 5 |
| POST   | `/reset`                     | 174-203 | 5 |
| GET    | `/audit/log`                 | 204-end | 5 |

---

## Copilot journey + journey builder

Source: [nexus-backend/src/apis/copilot_journey_api.py](../../nexus-backend/src/apis/copilot_journey_api.py)
Library target: **none** — stays in nexus-backend.

Reason: Copilot sessions and the journey-builder UI depend on nexus-backend's copilot engine,
which is out of the AI engine extraction scope. The reference server does not expose these
routes. Listed here only for completeness so no one accidentally ports them.

| Method | Path | Source lines | Disposition |
|--------|------|-------------|-------------|
| POST   | `/copilot-journey`                           | 71-83   | Stays in nexus-backend |
| POST   | `/copilot-journey/{session_id}/execute`      | 84-90   | Stays in nexus-backend |
| POST   | `/copilot-journey/{session_id}/feedback`     | 91-106  | Stays in nexus-backend |
| GET    | `/copilot-journey/{session_id}`              | 107-124 | Stays in nexus-backend |
| POST   | `/copilot-journey/{session_id}/save`         | 125-133 | Stays in nexus-backend |
| GET    | `/copilot-journey/{session_id}/stream`       | 134-159 | Stays in nexus-backend |
| POST   | `/journey-builder/suggest`                   | 160-174 | Stays in nexus-backend |
| POST   | `/journey-builder/validate`                  | 175-205 | Stays in nexus-backend |
| POST   | `/journey-builder/save`                      | 206-232 | Stays in nexus-backend |
| POST   | `/journey-builder/run`                       | 233-end | Stays in nexus-backend |

---

## MCP tools

Source:
- [nexus-backend/src/tools/journey_tool.py](../../nexus-backend/src/tools/journey_tool.py)
- [nexus-backend/src/tools/logs_and_reports_tool.py](../../nexus-backend/src/tools/logs_and_reports_tool.py)

Library target: `src/nexus_ai_engine/server/mcp.py` exposes both tools via FastMCP,
backed by library services. Tool schemas must match nexus-backend 1:1 so existing
MCP clients work unchanged.

---

## Health and infra routes (library-native)

Not ported from nexus-backend; these belong to the reference server itself.

| Method | Path | Phase |
|--------|------|-------|
| GET    | `/health`                     | 1 (this pass) |
| GET    | `/readiness`                  | 1 (this pass) |
| GET    | `/version`                    | 1 (this pass) |

---

## Base path

Nexus-backend mounts `journey_api.router` with prefix `/api/v1/journeys`,
`prompts_api.router` with `/api/v1/prompts`. The library's reference server mirrors those
prefixes so UIs and MCP clients don't need URL rewrites when a host app swaps in the
library's routers.
