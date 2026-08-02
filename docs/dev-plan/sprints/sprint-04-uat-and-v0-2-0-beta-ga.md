---
sprint: 4
title: "DSL compiler, journey CRUD, UAT and v0.2.0-beta GA"
release: v0.2.0-beta
duration: 2 weeks
dates: 2026-09-14 → 2026-09-25
status: Planned
---

# Sprint 4 — DSL compiler, journey CRUD, UAT and v0.2.0-beta GA

## Sprint goal

Compile DSL → ExecutionGraph, journey versioned CRUD, golden tests, **UAT β**, user guide Ch.3, cut **`0.2.0-beta`**.

## Backlog (44 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-4-1 | `journeys/compiler.py` → ExecutionGraph | 8 | EPIC-jrn-compiler |
| STORY-4-2 | Golden compile tests (5 journeys) | 5 | EPIC-jrn-compiler |
| STORY-4-3 | Journey service + CRUD API | 8 | EPIC-jrn-service |
| STORY-4-4 | Journey versioning immutability | 3 | EPIC-jrn-service |
| STORY-4-5 | `scripts/migrate-plugin-yaml.py` dry-run | 3 | EPIC-jrn-migration |
| STORY-4-6 | **Execute UAT β** | 8 | EPIC-doc-uat-beta |
| STORY-4-7 | **User guide Ch.3 Journey DSL Authoring** | 5 | EPIC-doc-userguide |
| STORY-4-8 | Cut `0.2.0-beta` | 2 | EPIC-plat-kube-operator |

## Definition of Done

- [ ] All example journeys compile
- [ ] UAT P0 100%; user guide Ch.3 merged

## Cross-references

- UAT: `docs/delivery/020-v0.2.0-beta-uat.md`
