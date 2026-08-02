---
id: ai-engine-dev-plan-kube-operator
title: kube-operator Integration for Nexus AI Engine
module: delivery
status: Accepted
version: "1.0.0"
owners: ["@nexus-platform/platform"]
depends_on: [ai-engine-dev-plan-master]
adrs: []
---

# kube-operator Integration for Nexus AI Engine

## Purpose

Nexus AI Engine is deployed as a **standalone capability** (`ai-engine`) via
nexus-deployer/kube-operator — the same pipeline pattern as **nexus-sre**, not
bundled into **nexus-ai** (ontology / VDL / Connector).

Example reference: `nexus-deployer/kube-operator/examples/nexus-ai-engine-complete.yaml`

## Pipeline

```text
bump-version.sh → package-images.sh → create-ecr-images.sh → app-rollout.sh
```

## Target repo layout (post S1)

```text
nexus-ai-engine/
  backend/
    VERSION
    Dockerfile
    pyproject.toml
    src/nexus_ai_engine/
  frontend/                    # from S11
    VERSION
    Dockerfile
    package.json
  deploy/k8s/                    # existing; extend for workers
  helm/ai-engine/                # from S10
```

## Required operator extensions (Sprint 2)

Add targets to all four kube-operator scripts:

| Target | VERSION file | Image name |
|---|---|---|
| `ai-engine-api` | `nexus-ai-engine/backend/VERSION` | `nexus-ai-engine-api` |
| `ai-engine-ui` | `nexus-ai-engine/frontend/VERSION` (S11+) | `nexus-ai-engine-ui` |
| `ai-engine-all` | both | both |

Rollout component: `ai-engine` or `ai-engine-api`, `ai-engine-ui`, `ai-engine-workers`.

## Deploy commands (GA reference)

```bash
cd nexus-deployer/kube-operator
./bump-version.sh ai-engine-api patch
./package-images.sh --only-ai-engine-api
./create-ecr-images.sh --only-ai-engine-images
./app-rollout.sh --capability ai-engine --env dev --version <tag> ai-engine-api
```

## Capability vs nexus-ai

| Capability | Repo | What it runs |
|---|---|---|
| `nexus-ai` | nexus-backend + nexus-ui | Ontology, VDL, Connector APIs |
| `nexus-sre` | nexus-sre | SRE planner / executor |
| **`ai-engine`** | **nexus-ai-engine** | Journey execution, tool compute, dev UI |

## Kubernetes namespace

| Env | Namespace |
|---|---|
| dev | `ai-engine-dev` |
| staging | `ai-engine-staging` |
| prod | `ai-engine` |

## Health gates (rollout)

- `GET /health` → 200
- `GET /readiness` → DynamoDB + tool registry reachable (from v0.2.0)
- Workers: Temporal poll active on `nexus-ai-execution` queue

## Cross-references

- `docs/spec/001-system-architecture.md` — physical deployment
- `docs/dev-plan/releases/v0.2.0-alpha-foundation.md` — S2 lands plumbing
