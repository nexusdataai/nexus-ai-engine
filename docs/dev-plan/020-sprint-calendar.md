---
id: ai-engine-dev-plan-sprint-calendar
title: Sprint Calendar — Nexus AI Engine
module: delivery
status: Accepted
version: "1.0.0"
owners: ["@nexus-platform/architects"]
depends_on: [ai-engine-dev-plan-master]
adrs: []
---

# Sprint Calendar — Nexus AI Engine

## Cadence

- Sprint length: **2 weeks**
- Start: **Monday 2026-08-04**
- Review + retro: **Friday** of week 2

## Team capacity

| Role | Headcount | Sprint capacity (h) |
|---|---|---|
| Backend / Executor | 2 | 256 |
| Frontend | 1 | 128 |
| Ontology integration (part-time from S7) | 0.5 | 64 |
| **Total focus** | ~3.5 FTE | ~448 h |

Target velocity: **45–60 story points / sprint** (after S2 calibration).

## Holiday & freeze windows

| Window | Dates | Effect |
|---|---|---|
| Winter buffer | 2026-12-21 → 2027-01-02 | No sprint; v0.2.0 prod cut before freeze |
| US Thanksgiving | 2026-11-23 → 2026-11-27 | S8 includes shortened week — scope locked in planning |

## Sprint calendar

| # | Release | Sprint dates | Demo / Retro | Release cut |
|---|---|---|---|---|
| 01 | v0.2.0-α | 2026-08-04 → 2026-08-14 | 2026-08-14 | — |
| 02 | v0.2.0-α | 2026-08-17 → 2026-08-28 | 2026-08-28 | **v0.2.0-alpha (2026-08-28)** |
| 03 | v0.2.0-β | 2026-08-31 → 2026-09-11 | 2026-09-11 | — |
| 04 | v0.2.0-β | 2026-09-14 → 2026-09-25 | 2026-09-25 | **v0.2.0-beta (2026-09-25)** |
| 05 | v0.2.0-rc1 | 2026-09-28 → 2026-10-09 | 2026-10-09 | — |
| 06 | v0.2.0-rc1 | 2026-10-12 → 2026-10-23 | 2026-10-23 | **v0.2.0-rc1 (2026-10-23)** |
| 07 | v0.2.0-rc2 | 2026-10-26 → 2026-11-06 | 2026-11-06 | — |
| 08 | v0.2.0-rc2 | 2026-11-09 → 2026-11-20 | 2026-11-20 | **v0.2.0-rc2 (2026-11-20)** |
| 09 | v0.2.0 | 2026-11-23 → 2026-12-04 | 2026-12-04 | — |
| 10 | v0.2.0 | 2026-12-07 → 2026-12-18 | 2026-12-18 | **v0.2.0 GA (2026-12-18)** |
| — | *holiday* | 2026-12-21 → 2027-01-02 | — | — |
| 11 | v0.3.0 | 2027-01-05 → 2027-01-16 | 2027-01-16 | — |
| 12 | v0.3.0 | 2027-01-19 → 2027-01-30 | 2027-01-30 | **v0.3.0 GA (2027-01-30)** |
| 13 | v1.0.0 | 2027-02-02 → 2027-02-13 | 2027-02-13 | — |
| 14 | v1.0.0 | 2027-02-16 → 2027-02-26 | 2027-02-26 | **v1.0.0 GA (2027-02-26)** |

## Prod deployment target (v1.0.0)

| Setting | Value |
|---|---|
| Namespace | `ai-engine` |
| Components | `nexus-ai-engine-api`, `nexus-ai-engine-ui`, `nexus-ai-engine-workers` |
| Pipeline | `nexus-deployer/kube-operator/app-rollout.sh --capability ai-engine` |

Adjust profile/cluster in `040-kube-operator-integration.md` per environment.
