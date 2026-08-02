---
sprint: 1
title: Contracts & monorepo scaffold
release: v0.2.0-alpha
duration: 2 weeks
dates: 2026-08-04 → 2026-08-14
status: Planned
---

# Sprint 1 — Contracts & monorepo scaffold

## Sprint goal

Land Pydantic contracts from `docs/spec/`, scaffold `backend/` layout, and green CI — unblocking all executor and DSL work in subsequent sprints.

## Backlog (38 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-1-1 | Repository skeleton per `002-repository-structure.md` | 5 | EPIC-plat-repo-scaffold |
| STORY-1-2 | Contracts: JourneyDefinition, ExecutionGraph, ToolRequest/Response | 8 | EPIC-plat-contracts |
| STORY-1-3 | JSON Schema export CLI | 3 | EPIC-plat-contracts |
| STORY-1-4 | Config loader (Pydantic Settings) + feature flags scaffold | 3 | EPIC-plat-config-loader |
| STORY-1-5 | CI workflow: ruff, pytest, mypy | 5 | EPIC-plat-ci-cd |
| STORY-1-6 | Contract round-trip tests | 5 | EPIC-plat-contracts |
| STORY-1-7 | ADR: AI Engine vs nexus-sre boundaries | 2 | EPIC-plat-repo-scaffold |
| STORY-1-8 | Draft UAT v0.2.0-alpha (`docs/delivery/010-*`) | 3 | EPIC-doc-uat-alpha |
| STORY-1-9 | Draft user guide outline (`docs/user-guide/000-*`) | 2 | EPIC-doc-userguide |

## Definition of Done

- [ ] `backend/src/nexus_ai_engine/contracts/` exports schemas
- [ ] CI green on main
- [ ] UAT alpha doc in Draft → Ready for S2 execution

## Demo

1. `python -m nexus_ai_engine.contracts.export` produces JSON schemas
2. `pytest tests/contracts/` green

## Cross-references

- `docs/spec/002`, `010`, `050`, `090`
- `docs/dev-plan/releases/v0.2.0-alpha-foundation.md`
