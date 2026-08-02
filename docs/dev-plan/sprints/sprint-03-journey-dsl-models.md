---
sprint: 3
title: Journey DSL models and validator
release: v0.2.0-beta
duration: 2 weeks
dates: 2026-08-31 → 2026-09-11
status: Planned
---

# Sprint 3 — Journey DSL models and validator

## Sprint goal

Implement full Journey DSL Pydantic models and semantic validator per `010-journey-dsl.md`.

## Backlog (40 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-3-1 | `contracts/journey_dsl.py` — Journey, Stage, Step | 8 | EPIC-jrn-dsl-models |
| STORY-3-2 | `journeys/validator.py` — schema validation | 5 | EPIC-jrn-validator |
| STORY-3-3 | Semantic rules: unique step ids, valid tool refs (warn) | 5 | EPIC-jrn-validator |
| STORY-3-4 | `POST /journeys/validate` endpoint | 3 | EPIC-api-journeys |
| STORY-3-5 | Unit tests: valid + invalid DSL fixtures | 5 | EPIC-jrn-validator |
| STORY-3-6 | Export `schemas/journey-dsl-v1.json` | 2 | EPIC-plat-contracts |
| STORY-3-7 | Draft UAT v0.2.0-beta | 3 | EPIC-doc-uat-beta |
| STORY-3-8 | Examples: 5 journey YAMLs in `examples/journeys/` | 5 | EPIC-jrn-dsl-models |

## Definition of Done

- [ ] Validator rejects malformed DSL with actionable errors
- [ ] UAT beta doc ready for S4

## Cross-references

- `docs/spec/010-journey-dsl.md`
