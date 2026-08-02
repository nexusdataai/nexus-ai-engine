# Chapter 2 — Embedded Dev UI

**Release:** v0.2.0-alpha  
**Status:** Draft — complete in Sprint 2  

## Purpose

The embedded Journey UI (v0.1) supports **development and port-forward testing**.
It is not the production operator UI (see Chapter 7 Journey Studio from v0.3.0).

## Pages

| Route | Purpose |
|-------|---------|
| `#/` | Journeys list |
| `#/journey/{id}` | Journey Studio (stages + steps) |
| `#/journey/{id}/jobs` | Job history + schedules |
| `#/schedules` | Cross-journey schedules |

## Common tasks

### Browse journeys

1. Open `/ui`
2. Use search and status filters on the grid
3. Click **Journey Studio** on a card

### Run a stage (simulated)

1. Open journey detail
2. Select a stage in the sidebar
3. Click **Start Processing**
4. Open **Logs** on a step to view SSE stream

### View job history

1. Navigate to **View All Jobs**
2. Click a row for the logs drawer

## Limitations

- In-memory state (restart clears unless seeded)
- No Cognito auth in embedded UI
- Production monitoring → v0.2.0 Executions API + v0.3.0 SPA

## Spec reference

- `docs/spec/UI.md`
- `docs/spec/ROUTE_PARITY.md`

---

*Add screenshots during UAT α: journeys grid, journey detail, job history.*
