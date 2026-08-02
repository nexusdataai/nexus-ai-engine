---
sprint: 11
title: Frontend shell and executions monitor
release: v0.3.0
duration: 2 weeks
dates: 2027-01-05 → 2027-01-16
status: Planned
---

# Sprint 11 — Frontend shell and executions monitor

## Sprint goal

Scaffold `frontend/` React SPA: dashboard, journeys list, executions monitor with SSE.

## Backlog (44 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-11-1 | Vite + React + TS + Tailwind scaffold | 5 | EPIC-ui-spa-scaffold |
| STORY-11-2 | App shell + React Router (nexus-sre pattern) | 5 | EPIC-ui-spa-scaffold |
| STORY-11-3 | Dashboard widgets (`GET /executions?status=RUNNING`) | 8 | EPIC-ui-dashboard |
| STORY-11-4 | Executions list + filters | 5 | EPIC-ui-dashboard |
| STORY-11-5 | Execution detail + SSE EventSource | 8 | EPIC-ui-dashboard |
| STORY-11-6 | Journeys list (parity with embedded UI) | 5 | EPIC-ui-dashboard |
| STORY-11-7 | kube-operator `ai-engine-ui` target | 5 | EPIC-plat-kube-operator |
| STORY-11-8 | Draft UAT v0.3.0 | 3 | EPIC-doc-uat-v030 |

## Cross-references

- `docs/spec/070-ui-specification.md`
