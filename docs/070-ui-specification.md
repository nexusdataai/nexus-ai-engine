# 070 — UI Specification (Journey Studio)

**Version:** 0.2.0  
**Status:** Draft  
**Evolves:** [docs/UI.md](../UI.md) (v0.1 embedded JSX UI)

---

## Purpose

Define the **Journey Studio** — a standalone React UI (nexus-sre pattern) for
managing journey DSL definitions and **monitoring all running executions**
across the AI Engine fleet.

---

## Design Goals

1. **Operational visibility** — see every running journey execution at a glance
2. **DSL management** — create, edit, validate, version journeys
3. **Live monitoring** — SSE-driven step progress, logs, approvals
4. **Parity with nexus-sre UX** — familiar patterns (sidebar, hub pages, detail shells)
5. **Standalone deploy** — separate UI pod or embedded static build

---

## Tech Stack (target — nexus-sre aligned)

| Layer | Choice |
|-------|--------|
| Framework | React 18 + TypeScript |
| Build | Vite |
| Styling | Tailwind CSS + Radix UI |
| Routing | React Router |
| Data | TanStack Query |
| Graph viz | ReactFlow (stage/step DAG) |
| Charts | Recharts (KPIs) |
| SSE | Native EventSource + reconnect |
| Tests | Vitest + Testing Library |

**Migration from v0.1:** Replace embedded JSX (`server/static/ui/app.js`) with
proper `frontend/` package; nginx or Vite build in Docker.

---

## Information Architecture

```text
/                           → Dashboard (executions overview)
/journeys                   → Journey list
/journeys/new               → Create journey (DSL editor)
/journeys/:id               → Journey detail (metadata + versions)
/journeys/:id/studio        → Journey Studio (stages/steps editor)
/journeys/:id/executions    → Execution history for journey
/executions                 → All executions (global monitor)
/executions/:id             → Execution detail (live graph + logs)
/schedules                  → Batch schedules
/prompts                    → Prompt catalog
/tools                      → Tool registry catalog (read-only)
/settings                   → Engine config display (read-only)
```

---

## Page Specifications

### Dashboard (`/`)

**Purpose:** Fleet-wide operational view.

| Widget | Data source |
|--------|-------------|
| Active executions count | `GET /executions?status=RUNNING` |
| Executions timeline (24h) | Aggregated metrics |
| Success rate by journey | Reports API |
| Failed executions alert list | `status=FAILED` |
| Worker queue depth | `/capabilities` or Prometheus proxy |
| Recent approvals pending | Executions with AWAITING_APPROVAL |

### Journey List (`/journeys`)

Existing v0.1 features retained:

- Search, filter by label/domain/status
- Cards with KPI summary (total runs, success rate, avg duration)
- Create / clone / delete actions

Added:

- Version badge
- "Active executions" pill per journey
- DSL validation status indicator

### Journey Studio (`/journeys/:id/studio`)

**Primary authoring surface.**

Layout (3-column):

```text
┌──────────────┬────────────────────────────┬──────────────┐
│ Stage list   │  Step editor / DSL view    │  Properties  │
│ (sidebar)    │  (center)                  │  (right)     │
│              │                            │              │
│ + Add stage  │  YAML editor OR form mode  │  tool picker │
│              │  ReactFlow graph preview   │  params      │
│              │                            │  retry       │
│              │  [Validate] [Save vN+1]    │  approval    │
└──────────────┴────────────────────────────┴──────────────┘
```

Actions:

- **Validate** — `POST /journeys/{id}/validate`
- **Save** — new version
- **Run** — `POST /executions` (full or selected stage)
- **Dry run** — compile only

Tool picker queries `GET /api/v1/tools` (registry proxy).

### Executions Monitor (`/executions`)

**Global running journeys view** — key new page.

| Column | Field |
|--------|-------|
| Execution ID | truncated UUID + link |
| Journey | name + version |
| Status | colored badge |
| Current stage | stage name |
| Progress | bar (nodes done / total) |
| Started | relative time |
| Duration | elapsed |
| Submitted by | user |
| Actions | pause / cancel |

Auto-refresh every 5s + SSE subscription for active rows.

Filters: status, journey_id, tenant, date range, label.

### Execution Detail (`/executions/:id`)

**Live monitoring shell** (like nexus-sre Incident Detail).

Sections:

1. **Header** — status badge, journey link, cancel/pause/resume
2. **Stage stepper** — horizontal progress through stages
3. **Graph view** — ReactFlow of steps with live node colors
4. **Logs drawer** — SSE stream (`/executions/{id}/stream`)
5. **Approval panel** — if AWAITING_APPROVAL
6. **Trace tab** — audit timeline
7. **Report tab** — post-completion summary

Node colors:

| NodeStatus | Color |
|------------|-------|
| PENDING | gray |
| RUNNING | blue pulse |
| SUCCEEDED | green |
| FAILED | red |
| SKIPPED | gray strikethrough |

### Tools Catalog (`/tools`)

Read-only view of registry tools:

- Name, description, risk_level, category
- JSON Schema parameters viewer
- Link to journeys using each tool

### Schedules / Prompts

Retain v0.1 functionality; add link from schedule → execution history.

---

## Real-Time Updates

```typescript
// hooks/useExecutionStream.ts
export function useExecutionStream(executionId: string) {
  // EventSource → /api/v1/executions/{id}/stream
  // Reconnect with Last-Event-ID
  // Parse state.transitioned, node.*, log events
  // Update TanStack Query cache
}
```

Multi-execution dashboard uses **one SSE per visible running execution**
(max 20) or polling fallback.

---

## Component Tree

```text
frontend/src/
├── pages/
│   ├── DashboardPage.tsx
│   ├── JourneysPage.tsx
│   ├── JourneyStudioPage.tsx
│   ├── ExecutionsPage.tsx          # NEW
│   ├── ExecutionDetailPage.tsx     # NEW
│   ├── SchedulesPage.tsx
│   ├── PromptsPage.tsx
│   └── ToolsCatalogPage.tsx        # NEW
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   └── PageHeader.tsx
│   ├── journeys/
│   │   ├── JourneyCard.tsx
│   │   ├── StageSidebar.tsx
│   │   └── DSLEditor.tsx
│   ├── executions/
│   │   ├── ExecutionGraphView.tsx  # ReactFlow
│   │   ├── StageStepper.tsx
│   │   ├── LiveLogDrawer.tsx
│   │   ├── NodeStatusBadge.tsx
│   │   └── ApprovalPanel.tsx
│   └── shared/
│       ├── StatusBadge.tsx
│       └── EmptyState.tsx
└── services/
    └── api.ts
```

---

## Deployment

### Option A: Separate UI pod (recommended — matches nexus-sre)

```text
Ingress /
  ├── /api/*  → nexus-ai-engine-api:8000
  └── /*      → nexus-ai-engine-ui:8080 (nginx)
```

### Option B: Embedded static (v0.1 compat)

FastAPI serves `frontend/dist/` at `/ui` for port-forward dev workflows.

---

## Auth Integration

UI expects JWT from host ingress (Cognito):

- Login page (or SSO redirect) — host-provided
- Token in `Authorization` header for API calls
- Role-based UI gates:
  - `ai-engine:executions:write` — submit/cancel
  - `ai-engine:journeys:write` — edit DSL
  - `ai-engine:approvals:write` — approve steps

---

## Migration from v0.1 Embedded UI

| v0.1 (app.js) | v0.2 (React SPA) |
|---------------|------------------|
| Hash routing | React Router |
| Inline JSX | TypeScript components |
| Job History | Executions + Stage Runs |
| Simulated demo stages | Real executor + registry |
| No global monitor | `/executions` dashboard |

Keep `/ui` redirect → new SPA during transition.

---

## Accessibility & UX

- Keyboard navigation in graph view
- Status not color-only (icons + text)
- Log drawer screen-reader friendly
- Dark theme default (match nexus-sre)

---

## Future Enhancements

- DSL diff viewer between versions
- Execution compare (two runs side-by-side)
- Drag-and-drop step builder
- Embedded approval notifications (webhook/Slack)
