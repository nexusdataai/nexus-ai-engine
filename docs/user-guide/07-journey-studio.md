# Journey Studio (v0.3.0)

The **Journey Studio** is the standalone React UI for managing journey DSL definitions and monitoring executions across the AI Engine fleet.

## Access

| Environment | URL |
|-------------|-----|
| Local dev | `http://127.0.0.1:5173` (Vite, proxies API to `:8000`) |
| Cluster UI pod | `nexus-ai-engine-ui` service on port 8080 |
| Embedded (legacy) | `http://<api-host>:8000/ui/` |

Sign in via **Cognito** (staging) or **Local** dev identity when `VITE_DEV_TOKEN` is configured.

## Dashboard

The home page shows:

- **Active executions** — count from `GET /api/v1/executions?status=RUNNING`
- **Total tracked** and **Failed** summaries
- A live list of running executions with links to detail pages

Auto-refresh runs every 5–10 seconds.

## Journey Studio

Navigate to **Journeys → Open studio** (or `/journeys/:id/studio`).

The three-column layout:

1. **Stages** — parsed from the YAML DSL
2. **DSL editor** — edit journey YAML directly
3. **Tool picker** — lists tools from `GET /api/v1/tools`

Actions:

- **Validate** — `POST /api/v1/journeys/validate`
- **Save** — `POST /api/v1/journeys/dsl`
- **Run** — `POST /api/v1/executions` then redirects to execution detail

## Executions monitor

**Executions** lists all runs with status badges. Click an execution ID to open the detail view:

- **Live graph** — ReactFlow visualization of step nodes
- **SSE event stream** — reconnecting `EventSource` on `/api/v1/executions/{id}/stream`
- **Cancel** — for non-terminal runs

## Tools catalog

**Tools** is a read-only catalog of published tool packages (`GET /api/v1/tools`). Filter by domain using the search box.

## Schedules

**Schedules** shows batch schedules from `GET /api/v1/schedules/`.

## Screenshots

See `docs/user-guide/images/v0.3.0/` for UAT capture set (dashboard, studio, executions, tools).

## Related

- Spec: `docs/spec/070-ui-specification.md`
- UAT: `docs/delivery/060-v0.3.0-uat.md`
- v0.2.0 Executions API (regression): `docs/user-guide/06-distributed-runtime.md`
