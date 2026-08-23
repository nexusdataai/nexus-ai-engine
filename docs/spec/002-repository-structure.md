# 002 — Repository Structure

**Version:** 0.2.0  
**Status:** Implemented  

---

## Purpose

Define the **monorepo layout** for `nexus-ai-engine`, aligned with
[`nexus-sre/docs/architecture/003-repository-structure.md`](../../nexus-sre/docs/architecture/003-repository-structure.md):
**domain-organized backend**, **separate frontend**, **sdk**, **deploy**, **tests**.

---

## Top-Level Layout

```text
nexus-ai-engine/
├── README.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── VERSION
├── CHANGELOG.md
│
├── backend/                    # Python service
│   ├── src/nexus_ai_engine/
│   ├── schemas/                # Exported JSON Schema contracts
│   └── .env.local.k3s.example
│
├── frontend/                   # Journey Studio React SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   └── Dockerfile
│
├── sdk/                        # Tool SDKs + sample packages
│   ├── nexus-tool-sdk/
│   ├── tools-o2c/
│   ├── python/                 # Placeholder for future client SDK
│   └── examples/
│       ├── journeys/
│       └── tool-packages/
│
├── deploy/                     # Docker, k8s, cloudformation, admin, docs
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── k8s/
│   ├── docs/                   # Specifications, UAT, user guide
│   └── admin/
│
├── scripts/                    # Dev helpers, migrations, lint
├── tests/                      # Unit, integration, e2e, BDD
└── .github/workflows/
```

---

## Backend Package Layout (domain-organized)

```text
backend/src/nexus_ai_engine/
├── app/                        # FastAPI bootstrap, lifespan, middleware
├── api/                        # HTTP routers (thin)
├── contracts/                  # Pydantic models = spec contracts
├── journeys/                   # Journey domain
├── executor/                   # Execution domain (core)
├── workers/                    # Distributed runtime (Temporal)
├── tools/                      # Tool integration (NOT implementations)
├── stages/                     # Stage handlers (legacy + plugin)
├── schedules/
├── prompts/
├── events/
├── adapters/                   # DynamoDB, S3, in-memory
├── mcp/
├── server/                     # Reference FastAPI app + CLI
├── testing/                    # Importable test harness
├── config.py
├── factory.py
└── errors.py
```

Tool implementations live in `sdk/` (`nexus-tool-sdk`, `tools-o2c`, etc.) and
are published to the engine via `POST /api/v1/tool-packages`.

---

## Frontend Layout

```text
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── pages/
│   ├── components/
│   ├── services/
│   └── hooks/
├── Dockerfile                  # nginx static
└── vite.config.ts
```

**Build integration:**

- **Dev:** Vite dev server proxies `/api` → FastAPI (`make dev-frontend`)
- **Prod:** Separate `nexus-ai-engine-ui` pod (nginx) + API pod

---

## SDK Layout

```text
sdk/
├── nexus-tool-sdk/             # VdlClient, ConnectorClient, ToolRuntime
├── tools-o2c/                  # O2C tool package
├── python/                     # Future HTTP client SDK
└── examples/
    ├── journeys/               # Sample Journey DSL YAML
    └── tool-packages/          # Sample publish manifests
```

Example journey run:

```bash
make journey JOURNEY=sdk/examples/journeys/order-to-cash-monitor.yaml
```

---

## Deploy Layout

```text
deploy/
├── Dockerfile                  # API image (build from repo root)
├── docker-compose.yml
├── k8s/                        # Kustomize manifests
├── cloudformation/
├── admin/                      # SSM seed, provisioning scripts
└── docs/                       # spec/, user-guide/, delivery/, dev-plan/
```

Build the API image:

```bash
docker build -f backend/Dockerfile -t nexus-ai-engine:local .
```

---

## What Stays a Library

The **`nexus_ai_engine` Python package** remains installable via pip for:

| Mode | Use case |
|------|----------|
| Embed services in-process | nexus-backend phase-10 migration |
| Mount routers in host FastAPI | Same-process HTTP |
| Testing harness | `nexus_ai_engine.testing` |

The monorepo layout adds the full-service structure around the library without
removing embedding modes.

---

## CODEOWNERS (proposed)

```
/backend/src/nexus_ai_engine/executor/   @nexus-platform/ai-engine
/backend/src/nexus_ai_engine/journeys/   @nexus-platform/ai-engine
/frontend/                               @nexus-platform/ai-engine-ui
/docs/                            @nexus-platform/ai-engine
/sdk/                                    @nexus-platform/ai-engine
```
