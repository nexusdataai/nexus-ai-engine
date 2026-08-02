# Chapter 1 — Getting Started

**Release:** v0.2.0-alpha  
**Status:** Accepted (Sprint 2)  
**UAT:** α-G1a (local), α-G1b (Kubernetes)

## What is Nexus AI Engine?

Nexus AI Engine is a **standalone shared execution service** that runs
**DSL-defined journeys** concurrently. Each journey step invokes a **ReAct tool**
loaded in the engine; tools reach data through the ontology **VDL** and **Connector**
APIs (via host applications in production).

For **v0.2.0-alpha**, the reference server ships with an **in-memory engine** and
demo journeys — ideal for local development and port-forward testing. DynamoDB-backed
persistence lands in v0.2.0.

## Prerequisites

| Tool | Local | Kubernetes |
|------|-------|------------|
| Python 3.12+ | Required | — |
| `curl` or HTTP client | Required | Required |
| `kubectl` | Optional | Required |
| AWS CLI + cluster access | — | Required (for deploy / context) |

**Repository layout (alpha monorepo):**

```text
nexus-ai-engine/
  backend/src/nexus_ai_engine/   # Python package
  backend/VERSION                # Semver for kube-operator pipeline
  deploy/k8s/                    # Production-shaped manifests (post-alpha)
```

---

## Quick start (local)

Use this path for day-to-day development and UAT scenarios **α-A***, **α-U***, **α-G1a**.

### 1. Install and run

```bash
cd /opt/mycode/nexus/nexus-ai-engine
make install-venv
source .venv/bin/activate
make serve
```

`make serve` starts the reference server on **port 8001** with `InMemoryEngine` and
seeded demo journeys (Order-to-Cash, Supply Chain Risk, Call Processing, etc.).

### 2. Open the embedded UI

In a browser: [http://localhost:8001/ui](http://localhost:8001/ui)

You should see a journey grid with search and status filters. See
[Chapter 2 — Embedded Dev UI](./02-embedded-dev-ui.md) for walkthrough tasks.

### 3. Verify the API

```bash
curl -sf http://localhost:8001/health | jq .
curl -sf http://localhost:8001/version | jq .
curl -sf http://localhost:8001/readiness | jq .
curl -sf http://localhost:8001/api/v1/journeys/ | jq 'length'
```

**Expected (alpha):**

| Endpoint | HTTP | Key checks |
|----------|------|------------|
| `/health` | 200 | `"status": "ok"` |
| `/version` | 200 | `"name": "nexus-ai-engine"` |
| `/readiness` | 200 | `"ready": true`, `"dynamodb": {"status": "skipped"}` |
| `/api/v1/journeys/` | 200 | Array length ≥ 1 (typically 5 seeded journeys) |
| `/ui` | 200 | HTML with embedded React UI |
| `/metrics` | 200 | Prometheus text; `nexus_ai_engine_build_info` |

### 4. Run automated smoke (optional)

```bash
make test-e2e-smoke    # health + UI static assets
pytest tests/e2e -q    # full API parity suite (47 tests)
```

---

## Quick start (Kubernetes)

Use this path when AI Engine is deployed to a cluster (UAT **α-G1b**, **α-D4**).

### 1. Select AWS + cluster context

From the deployer repo, pick your environment (Starhub BSSMagic / `prod-cluster` is
**index 3** in the sample registry):

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3
source .active-env
./set-context.sh --status
```

This logs into AWS, writes kubeconfig to `aws-login/.kube/config` (not `~/.kube/config`),
and exports `KUBECONFIG`, `AWS_PROFILE`, and `NEXUS_K8S_NAMESPACE`.

See [README-set-context.md](../../nexus-deployer/aws-login/README-set-context.md) for
multi-account setup.

### 2. Confirm the deployment

Alpha deploys the API image to namespace **`ai-engine-prod`**:

```bash
kubectl get pods -n ai-engine-prod
kubectl get svc -n ai-engine-prod
```

You should see `nexus-ai-engine` pods **Running** and service `nexus-ai-engine-api`
on port 8000.

### 3. Port-forward to your laptop

```bash
kubectl port-forward -n ai-engine-prod svc/nexus-ai-engine-api 8001:8000
```

Keep this terminal open. In another terminal:

```bash
curl -sf http://localhost:8001/health
open http://localhost:8001/ui    # or xdg-open / browser manually
```

The cluster pod runs the same in-memory reference server as local `make serve` for
alpha — seeded journeys and embedded UI behave the same via port-forward.

### 4. Deploy or upgrade (operators)

To build and roll out a new API image via kube-operator:

```bash
source /opt/mycode/nexus/nexus-deployer/aws-login/.active-env
cd /opt/mycode/nexus/nexus-deployer/kube-operator

./bump-version.sh ai-engine-api patch
./package-images.sh --only-ai-engine-api
./create-ecr-images.sh --only-ai-engine-images
./app-rollout.sh --capability ai-engine --env prod \
  --namespace ai-engine-prod ai-engine-api
```

Details: `docs/dev-plan/040-kube-operator-integration.md`

---

## Architecture (one paragraph)

Nexus AI Engine is the **compute plane**: it executes journeys, schedules jobs, and
streams logs. The **ontology data plane** (VDL queries, Connector calls) lives in
**nexus-backend** / **nexus-ai** — AI Engine invokes tools that reach those APIs.
See [docs/spec/000-ai-engine-overview.md](../spec/000-ai-engine-overview.md).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` on :8001 | Run `make serve` locally or start port-forward |
| `kubectl` uses wrong cluster | Re-run `./set-context.sh 3 && source .active-env` |
| Empty journey list | Restart server; seed data loads at startup |
| `/readiness` 503 locally | Engine not wired — check server logs |
| Port-forward dies | Re-run `kubectl port-forward ...`; check pod `Running` |

---

## Next steps

- [Chapter 2 — Embedded Dev UI](./02-embedded-dev-ui.md) — journey grid, jobs, SSE logs
- [UAT plan](../delivery/010-v0.2.0-alpha-uat.md) — sign-off matrix
- [ROUTE_PARITY](../spec/ROUTE_PARITY.md) — API routes used by the UI

---

*Verified: UAT α-G1a / α-G1b (2026-08-02). Screenshots: `images/v0.2.0-alpha/` (Ch.2).*
