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
K8S_NS        ?= nexus-ai-engine-dev
JOURNEY       ?= tests/journeys/samples/hello.yaml
BACKEND_SRC   := backend/src

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# -----------------------------------------------------------------------------
# Install / env
# -----------------------------------------------------------------------------

.PHONY: install
install: ## Install the package with all extras into the active environment
	$(PIP) install -e ".[dev,aws,test,server,harness]"

.PHONY: install-venv
install-venv: ## Create .venv if missing and install with all extras
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
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
export-schemas: ## Export JSON Schema files to schemas/
	$(PYTHON) -m nexus_ai_engine.contracts.export --out schemas/

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
	@mkdir -p reports
	behave tests/bdd/features -f pretty -f behave_html_formatter:HTMLFormatter -o reports/bdd.html

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
		--cov-report=term-missing --cov-report=html --cov-report=xml \
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
serve: ## Run the reference server on :8001 with in-memory adapters
	nexus-ai-engine serve --http --host 0.0.0.0 --port 8001

.PHONY: journey
journey: ## Execute a plugin-journey YAML end-to-end. Override with JOURNEY=path/to.yaml
	nexus-ai-engine run-journey $(JOURNEY)

# -----------------------------------------------------------------------------
# Docker / K8s
# -----------------------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build the reference-server image locally
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

.PHONY: docker-run
docker-run: ## Run the image on :8000
	docker run --rm -p 8000:8000 $(IMAGE_NAME):$(IMAGE_TAG)

.PHONY: compose-up
compose-up: ## docker-compose up (foreground)
	docker compose -f deploy/docker-compose.yml up --build

.PHONY: compose-down
compose-down: ## docker-compose down
	docker compose -f deploy/docker-compose.yml down

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
	rm -rf dist build *.egg-info .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov coverage.xml reports

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
