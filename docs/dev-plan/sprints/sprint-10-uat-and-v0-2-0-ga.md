---
sprint: 10
title: "Temporal workers, Executions API, UAT and v0.2.0 GA"
release: v0.2.0
duration: 2 weeks
dates: 2026-12-07 → 2026-12-18
status: Planned
---

# Sprint 10 — Temporal workers, Executions API, UAT and v0.2.0 GA

## Sprint goal

Distributed workers, full Executions API + SSE, 50 concurrent staging, **UAT v0.2.0**, user guide Ch.6, cut **`0.2.0`**.

## Backlog (46 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-10-1 | Temporal RunExecutionWorkflow + activities | 8 | EPIC-wkr-temporal |
| STORY-10-2 | Worker deployment + HPA Helm | 5 | EPIC-wkr-helm |
| STORY-10-3 | `/api/v1/executions` lifecycle | 8 | EPIC-api-executions |
| STORY-10-4 | SSE `/executions/{id}/stream` | 5 | EPIC-api-sse |
| STORY-10-5 | Admission controller concurrency limits | 5 | EPIC-wkr-admission |
| STORY-10-6 | MCP execution_tool | 3 | EPIC-api-mcp |
| STORY-10-7 | 50 concurrent executions staging test | 5 | EPIC-wkr-temporal |
| STORY-10-8 | **Execute UAT v0.2.0** | 8 | EPIC-doc-uat-v020 |
| STORY-10-9 | **User guide Ch.6 Monitoring + SSE** | 3 | EPIC-doc-userguide |
| STORY-10-10 | Cut `0.2.0` before holiday freeze | 2 | EPIC-plat-kube-operator |

## Definition of Done

- [ ] Execution survives worker pod kill
- [ ] UAT P0 100%

## Cross-references

- UAT: `docs/delivery/050-v0.2.0-uat.md`
