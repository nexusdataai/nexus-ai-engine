---
id: ai-engine-dev-plan-scrum-framework
title: Scrum Framework — Nexus AI Engine
module: delivery
status: Accepted
version: "1.0.0"
owners: ["@nexus-platform/architects"]
depends_on: [ai-engine-dev-plan-master]
adrs: []
---

# Scrum Framework — Nexus AI Engine

## Purpose

Defines how sprints are run so individual sprint plans stay focused on scope —
ceremonies, DoR/DoD, and working agreements are inherited from here.

## Roles

| Role | Responsibility | Filled by |
|---|---|---|
| **Product Owner** | Owns release exit criteria; approves sprint goals | Platform lead |
| **Scrum Master** | Ceremonies, blockers, DoR/DoD enforcement | Rotates per release |
| **Engineering team** | Delivers backlog; owns tests, docs, observability | 4 engineers |
| **Ontology liaison** | Reviews VDL/Connector API changes (from S7) | nexus-backend owner |
| **Docs reviewer** | User guide + spec alignment | @nexus-platform/architects |
| **QA / UAT coordinator** | UAT matrix execution on GA sprints | Product + QA |

## Ceremonies

| Ceremony | Cadence | Duration | Output |
|---|---|---|---|
| Sprint planning | Mon wk 1 | 90 min | Sprint plan `Accepted`; backlog frozen |
| Daily stand-up | Mon–Fri | 15 min | Blockers |
| Backlog refinement | Wed wk 1 | 60 min | Next sprint stories DoR-ready |
| Sprint review / demo | Fri wk 2 | 60 min | Demo recording; stakeholder sign-off |
| Sprint retrospective | Fri wk 2 pm | 45 min | Retro appended to sprint doc |
| Release cut | Last sprint of release | +30 min | Version bump, UAT sign-off, user guide merge |

## Working agreements

1. **Trunk-based development** — short-lived branches only.
2. **Every PR references a spec** — `docs/spec/NNN-*.md` or dev-plan story.
3. **Feature flags default off** in staging/prod until release cut.
4. **No LLM in executor tick loop** — ADR aligned with nexus-sre ADR-001.
5. **No in-process VirtualQueryService in tools** — use `nexus-tool-sdk` HTTP only (from rc2).
6. **UAT doc exists before GA sprint starts** — no release without UAT plan.
7. **User guide PR merges with GA** — same release PR or immediate follow-up.

## Definition of Ready (DoR)

- [ ] User story: "As a … I want … so that …"
- [ ] Acceptance criteria (Given/When/Then)
- [ ] Spec reference (`docs/spec/…`)
- [ ] Cross-module dependencies listed
- [ ] Story points (Fibonacci)
- [ ] UAT impact noted (new scenarios / regression)
- [ ] User guide impact noted (new section / screenshot)

## Definition of Done (DoD)

- [ ] Code merged; CI green
- [ ] Unit + integration tests; executor ≥ 90% where touched
- [ ] Spec or dev-plan updated if behaviour changed
- [ ] Metrics/logs for new API paths
- [ ] Deployed to `dev` via kube-operator
- [ ] Feature flag documented in ConfigMap
- [ ] **If GA sprint:** UAT P0 100%; user guide section published

## UAT gate (per release)

| Priority | Pass requirement | Blocker? |
|---|---|---|
| P0 | 100% pass | Yes — blocks GA |
| P1 | ≥ 90% pass | Waivable with PO + documented workaround |
| P2 | Best effort | No |

Evidence: screenshot or API trace linked in UAT sign-off matrix.

## User guide gate (per release)

Each GA sprint updates `docs/user-guide/`:

| Release | User guide deliverable |
|---|---|
| v0.2.0-alpha | Ch.1 Getting Started + Ch.2 Embedded Dev UI |
| v0.2.0-beta | Ch.3 Journey DSL Authoring |
| v0.2.0-rc1 | Ch.4 Executions API (CLI/API operator) |
| v0.2.0-rc2 | Ch.5 Tool Packages + Ontology Integration |
| v0.2.0 | Ch.6 Monitoring Executions + SSE |
| v0.3.0 | Ch.7 Journey Studio (full UI walkthrough) |
| v1.0.0 | Ch.8 Admin & Deployment + Ch.9 Troubleshooting |

## Story points

Target velocity: **45–60 points / sprint** (4 engineers, calibration S1–S2).

| Points | Meaning |
|---|---|
| 1 | Doc or config only |
| 2 | < 1 day, single module |
| 3 | Multi-file, includes tests |
| 5 | Cross-module, 2–4 days |
| 8 | Epic slice; 4–7 days |
| 13 | Split before accepting |
