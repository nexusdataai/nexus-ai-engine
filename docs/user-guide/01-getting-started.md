# Chapter 1 — Getting Started

**Release:** v0.2.0-alpha  
**Status:** Draft — complete in Sprint 2  

## What is Nexus AI Engine?

Nexus AI Engine is a **standalone shared execution service** that runs
**DSL-defined journeys** concurrently. Each journey step invokes a **ReAct tool**
loaded in the engine; tools reach data through the ontology **VDL** and **Connector**
APIs.

## Prerequisites

- Access to a cluster with AI Engine deployed (or local `make serve`)
- `kubectl` configured for port-forward (dev)
- curl or HTTP client

## Quick start (local)

```bash
cd nexus-ai-engine
make setup
make serve
# Open http://localhost:8001/ui
curl http://localhost:8001/health
curl http://localhost:8001/api/v1/journeys/
```

## Quick start (Kubernetes)

```bash
kubectl port-forward -n ai-engine svc/nexus-ai-engine-api 8001:8000
# Open http://localhost:8001/ui
```

## Architecture (one paragraph)

See `docs/spec/000-ai-engine-overview.md` for the compute plane vs ontology data
plane split.

## Next steps

- [Chapter 2 — Embedded Dev UI](./02-embedded-dev-ui.md)

---

*Updated: Sprint 2 (v0.2.0-alpha GA). Add screenshots in `images/v0.2.0-alpha/` during UAT.*
