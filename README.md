# nexus-ai-engine

Journey/stage/job AI orchestration engine extracted from `nexus-backend`.

Ships three things:

- A **library core** of port-based services for journeys, jobs, prompts, logs,
  reports, and SSE streaming. DynamoDB/S3 is the shipped default adapter;
  other adapters can be supplied by consumers.
- A **reference FastAPI + MCP server** (`nexus-ai-engine serve`) that composes
  the library into a standalone HTTP + MCP surface matching nexus-backend's
  existing API 1:1.
- An **importable testing harness** (`nexus_ai_engine.testing`) that lets any
  consumer exercise the engine in-process, including running plugin-journey
  YAMLs end-to-end, without a backend or AWS account.

## Status

**Pre-release (`0.1.0a1`).** The public API is not yet stable. Expect churn
during phases 2–9 of the extraction from
[`nexus-backend`](https://github.com/nexusdataai/nexus-backend) until `0.1.0`.

## Install

```bash
# From the internal Python index
pip install nexus-ai-engine

# Direct from GitHub (pin to a tag or main)
pip install "nexus-ai-engine @ git+https://github.com/nexusdataai/nexus-ai-engine.git@main"

# Editable, side-by-side with nexus-backend during development
pip install -e /path/to/nexus-ai-engine
```

Available extras:

```bash
pip install "nexus-ai-engine[aws]"      # boto3/botocore for the default adapters
pip install "nexus-ai-engine[server]"   # FastAPI + uvicorn + fastmcp + httpx
pip install "nexus-ai-engine[harness]"  # everything above + behave + pytest-benchmark
pip install "nexus-ai-engine[test,dev]" # full test + dev toolchain
```

## Package layout

```
src/nexus_ai_engine/
  config.py          # EngineConfig dataclass
  factory.py         # build_engine(config)
  errors.py          # EngineError + subclasses
  contracts/         # Protocol ports (repositories, sinks, events, scheduler, stage factory)
  models/            # Pydantic domain models (journey, prompt, logs/reports)
  stages/            # BaseStage, stage registry, PluginJourneyStage
  execution/         # TransformationJobExecutor, AsyncioJobScheduler
  services/          # JourneyService, PromptsService, LogsAndReportsService
  events/            # SSEManager / EventSink implementations
  adapters/          # DynamoDB, S3, in-memory shipped adapters
  server/            # Reference FastAPI app + routers + MCP + CLI
  testing/           # make_test_app, JourneyYAMLRunner, pytest fixtures plugin
```

## Quickstart — local reference server

```bash
make install-venv
source .venv/bin/activate
make serve                              # http://localhost:8001/health
```

Or via Docker:

```bash
make docker-build && make docker-run    # http://localhost:8000/health
```

Or docker-compose:

```bash
make compose-up
```

Routes return 501 until their owning phase of the extraction plan ports the
underlying service. See [docs/ROUTE_PARITY.md](docs/ROUTE_PARITY.md) for the
full inventory and phase mapping. Health, readiness, and version endpoints
are live today.

## Testing

The library is tested in complete isolation from nexus-backend and AWS — no
credentials, no network, no backend process required. See
[tests/README.md](tests/README.md) for the full tier guide.

```bash
make install-venv && source .venv/bin/activate
make test                # unit tests (<5s)
make test-all            # every tier (unit + integration + contract + property + e2e + journeys + bdd + endurance-smoke)
make coverage            # branch coverage with a 60% floor (ratcheting up per phase)
make journey             # run a sample plugin-journey YAML end-to-end
```

Tiered test directories:

- `tests/unit/`        fast Python-only tests
- `tests/integration/` moto-backed AWS adapter tests
- `tests/contract/`    parametrized across adapter implementations
- `tests/property/`    hypothesis state-machine tests
- `tests/e2e/`         in-process `httpx.AsyncClient` against the reference FastAPI app
- `tests/bdd/`         behave scenarios against the in-process harness
- `tests/endurance/`   concurrent load smoke (heavy scenarios opt-in)
- `tests/journeys/`    plugin-journey YAMLs exercised end-to-end

## Deployment as an independent pod

The reference server is packaged for Kubernetes. Manifests under
[deploy/k8s/](deploy/k8s/) provide a production-shaped Deployment + Service +
HPA + NetworkPolicy + ServiceAccount; the Dockerfile produces a <100MB
non-root image matching nexus-backend's conventions (python:3.12-slim, uid
1001, healthcheck on `/health`).

```bash
make docker-build
make k8s-apply             # kubectl apply -k deploy/k8s/
make k8s-smoke             # port-forward + curl /health
```

A GitHub Actions workflow
([`.github/workflows/deploy-eks.yml`](.github/workflows/deploy-eks.yml))
builds and pushes to ECR, then applies the manifests to the target EKS
cluster. It reuses nexus-backend's AWS infra — `AWS_ROLE_TO_ASSUME_DEV`,
cluster `nexus-dev`, region `us-east-1` — and deploys into the new namespace
`nexus-ai-engine-dev`. See [deploy/k8s/README.md](deploy/k8s/README.md) for
the complete checklist of AWS resources required before a live deploy.

## Development

```bash
make install-venv         # create .venv and install with all extras
source .venv/bin/activate
make watch                # TDD watch mode on unit tests
make lint                 # ruff
make typecheck            # mypy
make all                  # pre-push gate: clean + lint + typecheck + test-all + coverage + build
```

## License

MIT. See [LICENSE](LICENSE).
