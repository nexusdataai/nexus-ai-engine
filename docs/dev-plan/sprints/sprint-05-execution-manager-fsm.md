---
sprint: 5
title: ExecutionManager and FSM core
release: v0.2.0-rc1
duration: 2 weeks
dates: 2026-09-28 → 2026-10-09
status: Planned
---

# Sprint 5 — ExecutionManager and FSM core

## Sprint goal

Implement ExecutionManager tick loop and 101-aligned FSM per `020` and `021`.

## Backlog (42 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-5-1 | `executor/graph.py` ready-node scheduler | 5 | EPIC-exe-manager |
| STORY-5-2 | `executor/manager.py` + `engine.py` tick loop | 8 | EPIC-exe-manager |
| STORY-5-3 | FSM state transitions (journey/stage/step) | 8 | EPIC-exe-fsm |
| STORY-5-4 | FSM transition matrix tests | 5 | EPIC-exe-fsm |
| STORY-5-5 | Retry engine (backoff) | 5 | EPIC-exe-retry-approval |
| STORY-5-6 | Approval engine stub | 3 | EPIC-exe-retry-approval |
| STORY-5-7 | In-memory execution store | 5 | EPIC-exe-manager |
| STORY-5-8 | Draft UAT rc1 | 3 | EPIC-doc-uat-rc1 |

## Definition of Done

- [ ] FSM tests cover all transitions in `021`
- [ ] Mock graph executes without tools

## Cross-references

- `docs/spec/020-execution-engine.md`, `021-execution-state-machine.md`
