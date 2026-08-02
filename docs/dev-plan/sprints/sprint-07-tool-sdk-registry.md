---
sprint: 7
title: nexus-tool-sdk and Tool registry
release: v0.2.0-rc2
duration: 2 weeks
dates: 2026-10-26 → 2026-11-06
status: Planned
---

# Sprint 7 — nexus-tool-sdk and Tool registry

## Sprint goal

Ship `nexus-tool-sdk` and Tool base class; begin ontology VDL API promotion on nexus-backend.

## Backlog (41 pts)

| ID | Story | Pts | Epic |
|---|---|---|---|
| STORY-7-1 | `packages/nexus-tool-sdk/` VdlClient | 8 | EPIC-tool-sdk |
| STORY-7-2 | ConnectorClient + ToolRuntime | 5 | EPIC-tool-sdk |
| STORY-7-3 | Tool base class (nexus-sre aligned) | 5 | EPIC-tool-registry |
| STORY-7-4 | ToolRegistry in-memory + get/list | 5 | EPIC-tool-registry |
| STORY-7-5 | Ontology: promote `POST /api/v1/vdl/query` | 5 | EPIC-ont-vdl-api |
| STORY-7-6 | Ontology: `GET /api/v1/vdl/entities` | 3 | EPIC-ont-vdl-api |
| STORY-7-7 | SDK unit tests with httpx mock | 5 | EPIC-tool-sdk |
| STORY-7-8 | Draft UAT rc2 | 3 | EPIC-doc-uat-rc2 |

## Cross-references

- `docs/spec/040`, `041`
