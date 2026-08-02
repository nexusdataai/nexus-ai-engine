---
sprint: 8
title: "Tool packages, ontology wiring, UAT and v0.2.0-rc2 GA"
release: v0.2.0-rc2
duration: 2 weeks
dates: 2026-11-09 → 2026-11-20
status: Planned
---

# Sprint 8 — Tool packages, ontology wiring, UAT and v0.2.0-rc2 GA

## Sprint goal

Tool package publish, migrate O2C tools, ontology connector invoke API, **UAT rc2**, user guide Ch.5, cut **`0.2.0-rc2`**.

## Backlog (45 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-8-1 | `POST /api/v1/tool-packages` publish API | 8 | EPIC-tool-packages |
| STORY-8-2 | Package loader in worker/API startup | 5 | EPIC-tool-packages |
| STORY-8-3 | Migrate `tools-o2c` from nexus-backend | 8 | EPIC-tool-o2c-migrate |
| STORY-8-4 | ToolDispatcher → real packages + SDK | 5 | EPIC-exe-dispatcher |
| STORY-8-5 | Ontology: unified connector invoke API | 8 | EPIC-ont-connector-api |
| STORY-8-6 | Compiler strict tool validation | 3 | EPIC-jrn-compiler |
| STORY-8-7 | Contract tests SDK ↔ ontology OpenAPI | 3 | EPIC-ont-contract-tests |
| STORY-8-8 | **Execute UAT rc2** | 8 | EPIC-doc-uat-rc2 |
| STORY-8-9 | **User guide Ch.5 Tool Packages** | 3 | EPIC-doc-userguide |
| STORY-8-10 | Cut `0.2.0-rc2` | 2 | EPIC-plat-kube-operator |

## Definition of Done

- [ ] O2C match tool hits staging VDL over HTTP
- [ ] UAT P0 100%

## Cross-references

- UAT: `docs/delivery/040-v0.2.0-rc2-uat.md`
