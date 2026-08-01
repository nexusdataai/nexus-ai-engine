# Nexus AI Engine — Specification Index

**Version:** 0.3.0 (planning)  
**Status:** Draft  
**Owners:** Nexus Platform / AI Engine  

---

## Purpose

This directory is the **authoritative specification** for **Nexus AI Engine**
(`nexus-ai-engine`) — a standalone shared execution service that runs many
**DSL-defined journeys** concurrently. Each journey is composed of **stages**;
each stage contains **steps**; each step invokes a **ReAct tool** from the
**Tool Registry owned by AI Engine** (Python tool packages published by domain
ontology services).

Domain ontology services (future `nexus-ontology`; transitional: `nexus-backend`)
expose a **thin data plane** only: Virtual Data Layer (VDL) queries and
Connector invocations. All tool compute runs in AI Engine workers via
`nexus-tool-sdk`.

The AI Engine is the operational counterpart to:

| System | Role |
|--------|------|
| **nexus-sre Executor** | Deterministic infra remediation (PlannerResult → ExecutionGraph → tools) |
| **nexus-ai-engine** | Deterministic business/AI journeys (Journey DSL → ExecutionGraph → local ReAct tools) |
| **nexus-ontology (data plane)** | VDL + Connector APIs; schema, mappings, credentials — no production tool/journey execution |

Both executors share the **same execution semantics** (state machine, retries,
approvals, verification, distributed workers) defined in
[`nexus-sre/docs/executor`](../../nexus-sre/docs/executor) and
[`nexus-sre/docs/workflow`](../../nexus-sre/docs/workflow), adapted for
journey DSL and DynamoDB persistence.

---

## Document Map

| # | Document | Summary |
|---|----------|---------|
| 000 | [AI Engine Overview](./000-ai-engine-overview.md) | Vision, boundaries, positioning |
| 001 | [System Architecture](./001-system-architecture.md) | Components, deployment, integration topology |
| 002 | [Repository Structure](./002-repository-structure.md) | Monorepo layout (mirror nexus-sre) |
| 010 | [Journey DSL](./010-journey-dsl.md) | Journey / stage / step language |
| 020 | [Execution Engine](./020-execution-engine.md) | Executor components and tick loop |
| 021 | [Execution State Machine](./021-execution-state-machine.md) | Journey / stage / step FSM |
| 030 | [Distributed Worker Runtime](./030-distributed-worker-runtime.md) | Concurrent journey execution |
| 040 | [Tool Registry Integration](./040-tool-registry-integration.md) | AI Engine tool registry, packages, SDK |
| 041 | [Ontology Data Plane API](./041-ontology-data-plane-api.md) | VDL + Connector HTTP APIs |
| 050 | [Data Model & Storage](./050-data-model-and-storage.md) | DynamoDB, S3, events |
| 060 | [API Specification](./060-api-specification.md) | REST + SSE + MCP |
| 070 | [UI Specification](./070-ui-specification.md) | Journey Studio (React) |
| 080 | [Implementation Roadmap](./080-implementation-roadmap.md) | Phased refactor plan |
| 090 | [Nexus-SRE Executor Alignment](./090-nexus-sre-executor-alignment.md) | Spec crosswalk |

---

## Related External Specs

- [nexus-sre Executor Overview](../../nexus-sre/docs/executor/100-executor-overview.md)
- [nexus-sre Execution State Machine](../../nexus-sre/docs/executor/101-execution-state-machine.md)
- [nexus-sre Execution Graph Contract](../../nexus-sre/docs/contracts/020-execution-graph.md)
- [nexus-sre Distributed Workers](../../nexus-sre/docs/workflow/704-distributed-worker-runtime.md)
- [nexus-sre Temporal Integration](../../nexus-sre/docs/workflow/705-temporal-integration.md)
- [nexus-backend Control Plane / ReAct](../../nexus-backend/doc/control-plane/re-act-layer.md)

---

## Glossary

| Term | Definition |
|------|------------|
| **Journey** | A named, versioned DSL document: ordered stages with metadata |
| **Stage** | A logical phase within a journey (e.g. `entity_resolution`, `three_way_match`) |
| **Step** | Atomic unit of work: one ReAct tool invocation with params |
| **Run** | A single execution instance of one stage (maps to a Job today) |
| **Execution** | Top-level runtime record for a submitted journey (may span multiple stage runs) |
| **Tool** | Python `Tool` subclass loaded in AI Engine from a published tool package |
| **Tool Package** | Versioned manifest + wheel declaring tools and ontology API endpoints |
| **VDL** | Virtual Data Layer — query virtual entities by business name via ontology API |
| **Connector** | External system action (Salesforce, Webex, …) invoked via ontology API |
| **nexus-tool-sdk** | `VdlClient` + `ConnectorClient` used by tools running in AI Engine workers |
| **DSL** | YAML/JSON journey definition consumed by the engine (not LLM-generated at runtime) |
