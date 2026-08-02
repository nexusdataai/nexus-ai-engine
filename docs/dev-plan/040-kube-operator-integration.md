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

Nexus AI Engine ships container images (`nexus-ai-engine-api`, optional
`nexus-ai-engine-ui`, workers mode on api image) built and rolled out through
**existing** `nexus-deployer/kube-operator` scripts — same pattern as
nexus-sre and nexus-backend.

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
./bump-version.sh ai-engine-all patch
./package-images.sh --only-ai-engine-api --only-ai-engine-ui
./create-ecr-images.sh ai-engine-all
./app-rollout.sh --capability ai-engine --env staging
```

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
