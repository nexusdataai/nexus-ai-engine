---
sprint: 6
title: "ToolDispatcher mock, legacy bridge, UAT and v0.2.0-rc1 GA"
release: v0.2.0-rc1
duration: 2 weeks
dates: 2026-10-12 → 2026-10-23
status: Planned
---

# Sprint 6 — ToolDispatcher mock, legacy bridge, UAT and v0.2.0-rc1 GA

## Sprint goal

ToolDispatcher with EmbeddedToolRegistry; run O2C journey in-process; **UAT rc1**; user guide Ch.4; cut **`0.2.0-rc1`**.

## Backlog (43 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-6-1 | EmbeddedToolRegistry + mock O2C tools | 5 | EPIC-tool-embedded-mock |
| STORY-6-2 | ToolDispatcher dispatch loop | 5 | EPIC-exe-dispatcher |
| STORY-6-3 | LegacyStageAdapter for BaseStage | 8 | EPIC-exe-legacy-bridge |
| STORY-6-4 | End-to-end: compile + execute O2C with mocks | 8 | EPIC-exe-manager |
| STORY-6-5 | Verification + rollback minimal | 5 | EPIC-exe-retry-approval |
| STORY-6-6 | **Execute UAT rc1** | 8 | EPIC-doc-uat-rc1 |
| STORY-6-7 | **User guide Ch.4 Executions (API/CLI)** | 3 | EPIC-doc-userguide |
| STORY-6-8 | Cut `0.2.0-rc1` | 1 | EPIC-plat-kube-operator |

## Definition of Done

- [ ] O2C journey completes in-process
- [ ] UAT P0 100%

## Cross-references

- UAT: `docs/delivery/030-v0.2.0-rc1-uat.md`
