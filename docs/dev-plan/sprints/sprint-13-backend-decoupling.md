---
sprint: 13
title: Backend decoupling and observability
release: v1.0.0
duration: 2 weeks
dates: 2027-02-02 → 2027-02-13
status: Planned
---

# Sprint 13 — Backend decoupling and observability

## Sprint goal

nexus-backend Copilot submits to AI Engine; Grafana dashboards; deprecate prod embedded execution.

## Backlog (40 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-13-1 | AI Engine HTTP client in nexus-backend | 8 | EPIC-ga-backend-decouple |
| STORY-13-2 | Copilot: submit execution instead of execute_plan (prod flag) | 8 | EPIC-ga-backend-decouple |
| STORY-13-3 | Feature flag per tenant | 3 | EPIC-ga-backend-decouple |
| STORY-13-4 | Grafana dashboards (executions, queue, tool latency) | 5 | EPIC-plat-observability |
| STORY-13-5 | Alerts for failed executions + worker health | 5 | EPIC-plat-observability |
| STORY-13-6 | mTLS service mesh ontology ↔ engine | 5 | EPIC-ga-security-review |
| STORY-13-7 | Draft UAT v1.0.0 | 3 | EPIC-doc-uat-v100 |
| STORY-13-8 | **User guide Ch.8 Admin & Deployment** (draft) | 3 | EPIC-doc-userguide |

## Cross-references

- `docs/spec/080-implementation-roadmap.md` phase 10
