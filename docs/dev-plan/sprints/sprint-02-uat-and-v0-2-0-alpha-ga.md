---
sprint: 2
title: "Embedded UI, operator plumbing, UAT and v0.2.0-alpha GA"
release: v0.2.0-alpha
duration: 2 weeks
dates: 2026-08-17 → 2026-08-28
status: Planned
---

# Sprint 2 — Embedded UI, operator plumbing, UAT and v0.2.0-alpha GA

## Sprint goal

Extend kube-operator for `ai-engine-api`, harden embedded UI, **execute UAT α**, publish user guide Ch.1–2, cut **`0.2.0-alpha`**.

## Backlog (42 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-2-1 | kube-operator: `ai-engine-api` targets in 4 scripts | 5 | EPIC-plat-kube-operator |
| STORY-2-2 | `/readiness` + `/version` + metrics on API | 3 | EPIC-plat-observability |
| STORY-2-3 | Embedded UI route parity audit vs `ROUTE_PARITY.md` | 5 | EPIC-ui-embedded |
| STORY-2-4 | Seed journeys polish (O2C, supply-chain samples) | 3 | EPIC-ui-embedded |
| STORY-2-5 | E2E: health + journeys + UI smoke | 5 | EPIC-plat-ci-cd |
| STORY-2-6 | Deploy to dev via kube-operator | 3 | EPIC-plat-kube-operator |
| STORY-2-7 | **Execute UAT P0/P1** (`010-v0.2.0-alpha-uat.md`) | 8 | EPIC-doc-uat-alpha |
| STORY-2-8 | **User guide Ch.1 Getting Started + Ch.2 Dev UI** | 5 | EPIC-doc-userguide |
| STORY-2-9 | Cut `0.2.0-alpha` + CHANGELOG | 3 | EPIC-plat-kube-operator |
| STORY-2-10 | Release notes + spec status update | 2 | EPIC-doc-userguide |

## Definition of Done

- [ ] UAT sign-off matrix complete (P0 100%)
- [ ] User guide Ch.1–2 merged
- [ ] `0.2.0-alpha` on dev cluster
- [ ] `./app-rollout.sh --capability ai-engine --env dev` succeeds

## Demo

1. Port-forward → `/ui` shows journey grid
2. UAT evidence linked in delivery doc
3. User guide rendered locally

## Cross-references

- UAT: `docs/delivery/010-v0.2.0-alpha-uat.md`
- Build: `docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md`
