---
id: ai-engine-dev-plan-index
title: Nexus AI Engine Development Plan
module: delivery
status: Accepted
version: "1.0.0"
owners: ["@nexus-platform/architects", "@nexus-ai-engine/platform"]
depends_on: [ai-engine-spec-index]
adrs: []
---

# Nexus AI Engine Development Plan

## Purpose

This directory is the **scrum-level execution plan** for building **Nexus AI Engine**
(`nexus-ai-engine`). It converts the specifications in `docs/spec/` — especially
`080-implementation-roadmap.md`, `040-tool-registry-integration.md`, and
`041-ontology-data-plane-api.md` — into a concrete sequence of two-week sprints.

Each release includes:

- Backend + frontend (or embedded UI → SPA) delivery
- **UAT** test plan in `docs/delivery/` and execution in the final sprint of the release
- **User guide** updates in `docs/user-guide/`
- **Cursor build plan** in `/root/.cursor/plans/` (mirrored under `docs/dev-plan/build/`)

## Product shape

| Component | Repo folder | Stack | Deployed image |
|---|---|---|---|
| **`nexus-ai-engine-api`** | `backend/` (target) | Python 3.12, FastAPI, Temporal worker, Pydantic v2, DynamoDB, S3 | `nexus-ai-engine-api:<semver>-<sha>` |
| **`nexus-ai-engine-ui`** | `frontend/` (target) | React 18, Vite, TypeScript, Tailwind (from v0.3.0) | `nexus-ai-engine-ui:<semver>-<sha>` |
| **`nexus-ai-engine-workers`** | `backend/` workers entrypoint | Same image, `worker` mode | `nexus-ai-engine-api:<semver>-<sha>` |

Deployment uses **`nexus-deployer/kube-operator`**: `bump-version.sh` →
`package-images.sh` → `create-ecr-images.sh` → `app-rollout.sh`.

## Reading order

1. `000-master-plan.md` — top-level scrum roadmap (read first)
2. `010-scrum-framework.md` — ceremonies, roles, DoR/DoD
3. `020-sprint-calendar.md` — sprint dates and release cuts
4. `030-epics-and-backlog.md` — epics mapped to sprints
5. `040-kube-operator-integration.md` — operator pipeline extensions
6. `releases/` — one plan per product release (`v0.2.0-alpha` … `v1.0.0`)
7. `sprints/` — one plan per sprint (`sprint-01-…` … `sprint-14-…`)
8. `build/` — Cursor-style build plans (YAML todos) per release
9. `../delivery/` — UAT plans per release
10. `../user-guide/` — operator and admin documentation

## Directory map

| Path | Purpose |
|---|---|
| `000-master-plan.md` | Master scrum plan across seven product releases |
| `010-scrum-framework.md` | Ceremonies, roles, DoR/DoD |
| `020-sprint-calendar.md` | Sprint schedule with dates and release cuts |
| `030-epics-and-backlog.md` | Epic inventory and sprint crosswalk |
| `040-kube-operator-integration.md` | kube-operator extensions for AI Engine images |
| `releases/v0.2.0-alpha-foundation.md` | Sprint 1–2 |
| `releases/v0.2.0-beta-journey-dsl.md` | Sprint 3–4 |
| `releases/v0.2.0-rc1-execution-engine.md` | Sprint 5–6 |
| `releases/v0.2.0-rc2-tool-platform.md` | Sprint 7–8 |
| `releases/v0.2.0-distributed-runtime.md` | Sprint 9–10 |
| `releases/v0.3.0-journey-studio.md` | Sprint 11–12 |
| `releases/v1.0.0-production-ga.md` | Sprint 13–14 |
| `sprints/sprint-NN-*.md` | Per-sprint goal, backlog, DoD, demo |
| `build/v*.plan.md` | Build plans with backend/UI/UAT/user-guide todos |

## Cross-references

- `docs/spec/README.md` — specification index
- `docs/spec/080-implementation-roadmap.md` — phase-level roadmap
- `docs/spec/040-tool-registry-integration.md` — local tool registry + publish pipeline
- `docs/spec/041-ontology-data-plane-api.md` — VDL + Connector APIs
- `docs/delivery/` — UAT plans per release
- `docs/user-guide/` — operator documentation

## Status

`Accepted` for the planning structure. Sprint retros are appended in place after
each sprint completes.
