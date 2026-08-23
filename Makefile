.DEFAULT_GOAL := help

PYTHON        ?= python3
PIP           ?= $(PYTHON) -m pip
VENV          := .venv
VENV_BIN      := $(VENV)/bin
PYTEST        ?= pytest
# Branch-coverage floor enforced by `make coverage`. Raised incrementally
# with the test-surface phases:
#   - 50  : current (after P1–P6 test expansion in phase-1 scope)
#   - 75  : target once adapter-layer tests (phase 7) land
#   - 85  : target once service-layer logic moves out of in_memory_engine
# The pytest-cov counter undercounts declarative Pydantic models
# (class bodies execute before `--cov` instruments the module). Treat
# this as a floor, not a coverage goal.
COV_FAIL      ?= 50
IMAGE_NAME    ?= nexus-ai-engine
IMAGE_TAG     ?= local
K8S_NS        ?= ai-engine-dev
JOURNEY       ?= tests/journeys/samples/hello.yaml
BACKEND_SRC   := backend/src
OPERATOR_DIR  := ../nexus-deployer/kube-operator
AI_ENGINE_DIR := $(CURDIR)
KUBE_CONTEXT  ?= local-cluster
NAMESPACE     ?= ai-engine-dev
ENV           ?= dev

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# -----------------------------------------------------------------------------
# Install / env
# -----------------------------------------------------------------------------

.PHONY: install
install: ## Install the package with all extras into the active environment
	$(PIP) install -e sdk/nexus-tool-sdk
	$(PIP) install -e sdk/tools-o2c
	$(PIP) install -e ".[dev,aws,test,server,harness]"

.PHONY: install-venv
install-venv: ## Create .venv if missing and install with all extras
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -e sdk/nexus-tool-sdk
	$(VENV_BIN)/pip install -e sdk/tools-o2c
	$(VENV_BIN)/pip install -e ".[dev,aws,test,server,harness]"
	@echo "Activate with: source $(VENV_BIN)/activate"

# -----------------------------------------------------------------------------
# Tests — tiered
# -----------------------------------------------------------------------------

.PHONY: test
test: ## Fast path: unit tests only
	$(PYTEST) tests/unit -q

.PHONY: test-unit
test-unit: ## Run unit tests
	$(PYTEST) tests/unit -q

.PHONY: test-contracts
test-contracts: ## Run Pydantic contract tests
	$(PYTEST) tests/contracts -q

.PHONY: export-schemas
export-schemas: ## Export JSON Schema files to backend/schemas/
	$(PYTHON) -m nexus_ai_engine.contracts.export --out backend/schemas/

.PHONY: test-integration
test-integration: ## Run integration tests (moto-backed)
	$(PYTEST) tests/integration -q

.PHONY: test-contract
test-contract: ## Run cross-adapter contract tests
	$(PYTEST) tests/contract -q

.PHONY: test-property
test-property: ## Run hypothesis property tests
	$(PYTEST) tests/property -q --hypothesis-show-statistics

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests against the in-process reference server
	$(PYTEST) tests/e2e -q

.PHONY: test-e2e-smoke
test-e2e-smoke: ## Minimal alpha smoke: health, journeys API, embedded UI assets
	$(PYTEST) tests/e2e/test_health.py tests/e2e/test_ui_static.py -q

.PHONY: test-journeys
test-journeys: ## Exercise plugin-journey YAML samples end-to-end
	$(PYTEST) tests/journeys -q

.PHONY: test-bdd
test-bdd: ## Run behave BDD scenarios against the in-process harness
	@mkdir -p tests/reports
	behave tests/bdd/features -f pretty -f behave_html_formatter:HTMLFormatter -o tests/reports/bdd.html

.PHONY: test-endurance
test-endurance: ## Run endurance smoke (skips @heavy)
	$(PYTEST) tests/endurance -q -m "not heavy"

.PHONY: test-endurance-full
test-endurance-full: ## Run the full endurance suite (incl. @heavy)
	$(PYTEST) tests/endurance -q

.PHONY: test-all
test-all: ## Run every tier sequentially
	$(PYTEST) tests/unit tests/integration tests/contract tests/property tests/e2e tests/journeys tests/endurance -q -m "not heavy"
	$(MAKE) test-bdd

.PHONY: coverage
coverage: ## Run the suite with branch coverage and HTML+XML reports
	$(PYTEST) tests/unit tests/integration tests/contract tests/property tests/e2e tests/journeys \
		--cov=nexus_ai_engine --cov-branch \
		--cov-report=term-missing --cov-report=html:tests/htmlcov --cov-report=xml:tests/coverage.xml \
		--cov-fail-under=$(COV_FAIL)

.PHONY: watch
watch: ## TDD watch mode for unit tests
	ptw --runner "$(PYTEST) -q tests/unit"

.PHONY: parallel
parallel: ## Run the suite in parallel
	$(PYTEST) -n auto

# -----------------------------------------------------------------------------
# Lint / typecheck / boundary
# -----------------------------------------------------------------------------

.PHONY: lint-docs
lint-docs: ## Validate YAML front-matter on planning/delivery docs
	$(PYTHON) scripts/lint_doc_frontmatter.py

.PHONY: lint-ci
lint-ci: ## Ruff lint for CI gate (contracts + contract tests)
	ruff check $(BACKEND_SRC)/nexus_ai_engine/contracts tests/contracts

.PHONY: lint
lint: ## Ruff lint
	ruff check $(BACKEND_SRC) tests

.PHONY: format
format: ## Ruff format in place
	ruff format $(BACKEND_SRC) tests

.PHONY: format-check
format-check: ## Verify formatting without changes
	ruff format --check $(BACKEND_SRC) tests

.PHONY: typecheck
typecheck: ## Mypy on library source
	mypy $(BACKEND_SRC)/nexus_ai_engine

.PHONY: guardrail
guardrail: ## Boundary check: no imports from nexus-backend
	@set -e; \
	if grep -RIn --include='*.py' -E '^\s*(from|import)\s+src(\.|\s)' $(BACKEND_SRC) tests; then \
		echo "ERROR: Library must not import from 'src.*' (nexus-backend internal layout)."; exit 1; \
	fi; \
	if grep -RIn --include='*.py' -E '^\s*(from|import)\s+nexus_backend(\.|\s)' $(BACKEND_SRC) tests; then \
		echo "ERROR: Library must not import from nexus_backend."; exit 1; \
	fi; \
	echo "OK: no nexus-backend imports detected."

# -----------------------------------------------------------------------------
# Local run
# -----------------------------------------------------------------------------

.PHONY: serve
serve: ## Run the reference server on :8000 with in-memory adapters
	nexus-ai-engine serve --http --host 0.0.0.0 --port 8000

.PHONY: journey
journey: ## Execute a plugin-journey YAML end-to-end. Override with JOURNEY=path/to.yaml
	nexus-ai-engine run-journey $(JOURNEY)

# -----------------------------------------------------------------------------
# K3s local dev (host-run backend/frontend against port-forwarded services)
# -----------------------------------------------------------------------------

.PHONY: port-forward-k3s stop-port-forward-k3s verify-k3s-dev ensure-k3s-dev init-k3s-local-aws
.PHONY: dev-backend dev-backend-setup dev-frontend dev-frontend-setup
.PHONY: package push apply-k8s rollout deploy-dev smoke

port-forward-k3s:
	./scripts/port-forward-k3s-dev.sh --kube-context $(KUBE_CONTEXT)

stop-port-forward-k3s:
	./scripts/stop-port-forward-k3s-dev.sh

verify-k3s-dev:
	./scripts/verify-k3s-dev-services.sh

ensure-k3s-dev:
	./scripts/ensure-k3s-dev-port-forwards.sh --kube-context $(KUBE_CONTEXT)

init-k3s-local-aws: ensure-k3s-dev
	unset AWS_PROFILE AWS_DEFAULT_PROFILE; \
	AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
	python3 $(OPERATOR_DIR)/scripts/local_init_aws.py \
	  --capabilities ai-engine \
	  --environment local \
	  --scylla-endpoint http://127.0.0.1:8001 \
	  --minio-endpoint http://127.0.0.1:9000 \
	  --ministack-endpoint http://127.0.0.1:4566

.PHONY: seed-k3s-dev-journeys recreate-k3s-journeys-table
seed-k3s-dev-journeys: dev-backend-setup ## Seed 5 demo journeys into local DynamoDB (when table is empty)
	@curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 || { echo "ERROR: Backend not running on :8000. Start: make dev-backend"; exit 1; }
	PATH="$(VENV_BIN):$$PATH" ./scripts/seed-sample-journeys.sh --base http://127.0.0.1:8000

recreate-k3s-journeys-table: ensure-k3s-dev ## Drop and recreate ai-engine-local-journeys (fixes GSI schema); then seed
	unset AWS_PROFILE AWS_DEFAULT_PROFILE; \
	AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin AWS_DEFAULT_REGION=us-east-1 \
	aws dynamodb delete-table --table-name ai-engine-local-journeys --endpoint-url http://127.0.0.1:8001 || true; \
	sleep 3; \
	$(MAKE) init-k3s-local-aws

dev-backend-setup:
	@test -f backend/.env.local || cp backend/.env.local.k3s.example backend/.env.local
	$(MAKE) install-venv

dev-backend: dev-backend-setup ensure-k3s-dev init-k3s-local-aws
	unset AWS_PROFILE AWS_DEFAULT_PROFILE; \
	. $(VENV_BIN)/activate && \
	set -a && . backend/.env.local && set +a && \
	nexus-ai-engine serve --http --host $${API_HOST:-0.0.0.0} --port $${API_PORT:-8000}

dev-frontend-setup:
	@test -f frontend/.env.local || cp frontend/.env.local.k3s.example frontend/.env.local
	cd frontend && npm ci

dev-frontend: dev-frontend-setup
	@curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 || { echo "ERROR: Backend not running on :8000. Start it first: make dev-backend"; exit 1; }
	cd frontend && npm run dev

package:
	$(OPERATOR_DIR)/package-images.sh --only-ai-engine-images --ai-engine-dir $(AI_ENGINE_DIR)

push:
	$(OPERATOR_DIR)/create-ecr-images.sh --only-ai-engine-images

apply-k8s:
	kubectl apply -k deploy/k8s/ -n $(NAMESPACE) --server-side || \
	kubectl apply -k deploy/k8s/

rollout:
	$(OPERATOR_DIR)/app-rollout.sh --capability ai-engine --env $(ENV) --namespace $(NAMESPACE) ai-engine-all

deploy-dev: package push apply-k8s rollout

smoke:
	kubectl exec -n $(NAMESPACE) deploy/nexus-ai-engine -- curl -sf http://127.0.0.1:8000/health
	kubectl exec -n $(NAMESPACE) deploy/nexus-ai-engine-ui -- wget -qO- --timeout=5 http://127.0.0.1:8080/ >/dev/null

# -----------------------------------------------------------------------------
# Docker / K8s
# -----------------------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build the reference-server image locally
	docker build -f backend/Dockerfile -t $(IMAGE_NAME):$(IMAGE_TAG) .

.PHONY: docker-run
docker-run: ## Run the image on :8000
	docker run --rm -p 8000:8000 $(IMAGE_NAME):$(IMAGE_TAG)

.PHONY: compose-up
compose-up: ## docker-compose up (foreground)
	docker compose -f scripts/legacy-deploy/docker-compose.yml up --build

.PHONY: compose-down
compose-down: ## docker-compose down
	docker compose -f scripts/legacy-deploy/docker-compose.yml down

.PHONY: k8s-apply
k8s-apply: ## Apply K8s manifests to the current kubectl context
	kubectl apply -k deploy/k8s/

.PHONY: k8s-smoke
k8s-smoke: ## Port-forward to the service and hit /health
	@kubectl -n $(K8S_NS) port-forward svc/nexus-ai-engine 18000:8000 & \
	sleep 2; \
	curl -fsS http://localhost:18000/health; echo; \
	kill %1 2>/dev/null || true

# -----------------------------------------------------------------------------
# Build / clean / CI
# -----------------------------------------------------------------------------

.PHONY: build
build: ## Build sdist + wheel into dist/
	$(PYTHON) -m build

.PHONY: clean
clean: ## Remove caches and build artifacts
	rm -rf dist build *.egg-info .pytest_cache .ruff_cache .mypy_cache .coverage tests/coverage.xml tests/htmlcov tests/reports

.PHONY: ci
ci: ## What CI runs: guardrail + lint + lint-docs + typecheck + coverage + build
	$(MAKE) guardrail
	$(MAKE) lint
	$(MAKE) lint-docs
	$(MAKE) typecheck
	$(MAKE) coverage
	$(MAKE) build

.PHONY: all
all: clean guardrail lint typecheck test-all coverage build ## Pre-push gate
