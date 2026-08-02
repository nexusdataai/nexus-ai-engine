# 010 — Journey DSL Specification

**Version:** 0.2.0  
**Status:** Draft  
**Schema URL:** `nexus.ai/contracts/journey-dsl/v1`

---

## Purpose

Define the **Journey DSL** — a declarative YAML/JSON format for describing
multi-stage workflows where each **step** invokes a **ReAct tool** from the
Tool Registry.

The DSL is:

- **Authored** by humans, Copilot, or plugin generators (not LLM-generated at runtime)
- **Validated** at submit time (JSON Schema + semantic checks)
- **Compiled** into an `ExecutionGraph` (nexus-sre contract) for execution
- **Versioned** and stored in DynamoDB

---

## Document Structure

```yaml
apiVersion: nexus.ai/v1
kind: Journey
metadata:
  id: order-to-cash-monitor              # unique, stable
  version: 3                             # monotonic integer
  tenant_id: tenant-acme                 # optional multi-tenant
  labels:
    domain: finance
    oda: order-management
  created_at: "2026-08-01T00:00:00Z"
  updated_at: "2026-08-01T12:00:00Z"

spec:
  display_name: Order-to-Cash Monitor
  description: >
    Monitors O2C pipeline: entity resolution → three-way match → exceptions.
  trigger: manual                        # manual | schedule | event
  schedule: "0 6 * * *"                  # cron, if trigger=schedule

  defaults:
    retry:
      max_attempts: 3
      initial_backoff_s: 2
      max_backoff_s: 60
    timeout_s: 300
    on_failure: abort                      # abort | continue | rollback

  concurrency:
    max_parallel_runs: 2                 # concurrent executions of this journey
    max_parallel_steps: 4                # within a stage graph

  variables:                             # journey-level constants
    s3_prefix: "analytics/o2c"
    tolerance_pct: 0.01

  stages:
    - id: entity_resolution
      name: Entity Resolution
      description: Resolve CRM entities for matching
      depends_on: []                     # stage-level DAG (optional)
      steps:
        - id: fetch_opportunities
          tool: query_virtual_entity
          params:
            entity: Opportunity
            filter:
              stage: Closed Won
            limit: 500
          output: opportunities            # binds $opportunities

        - id: enrich_accounts
          tool: soql_query
          foreach: "$opportunities.items"
          params:
            query: "SELECT Id, Name FROM Account WHERE Id = '$item.AccountId'"
          output: enriched

    - id: three_way_match
      name: Three-Way Match
      depends_on: [entity_resolution]
      requires_approval: false
      steps:
        - id: match_rows
          tool: o2c_match_order_delivery_invoice
          foreach: "$entity_resolution.enriched.items"
          params:
            opportunity_id: "$item.Opportunity_ID"
          retry:
            max_attempts: 5
          verification:
            - check_id: match_rate
              expression: "$result.match_rate >= 0.95"
              on_failure: warn

        - id: write_exceptions
          tool: s3_write_exceptions          # hypothetical write tool
          type: compute                      # non-tool step kinds (see below)
          condition: "$match_rows.exceptions | length > 0"
          params:
            path: "$variables.s3_prefix/exceptions/"
            data: "$match_rows.exceptions"
          requires_approval: true
          risk_class: write
```

---

## Entity Hierarchy

```text
Journey
 └── Stage[]          (ordered / DAG via depends_on)
      └── Step[]      (compiled to ExecutionNode[])
```

| Entity | Identity | Mutable at runtime? |
|--------|----------|---------------------|
| Journey | `metadata.id` + `metadata.version` | Definition immutable; new version = new record |
| Stage | `stage.id` within journey | Frozen in execution snapshot |
| Step | `step.id` within stage | Frozen in execution snapshot |
| Execution | UUID generated at submit | Runtime state in DynamoDB |
| StageRun | UUID per stage invocation | Legacy: Job |

---

## Step Types

| Kind | Field | Execution |
|------|-------|-----------|
| **ReAct tool** | `tool: <registry_name>` | `ToolDispatcher → nexus-backend` |
| **Compute** | `type: compute` + `logic:` | In-engine sandbox (JMESPath / CEL subset) |
| **Verify** | `type: verify` | Maps to `NodeKind.VERIFY` |
| **Approval** | `type: approval` | Maps to `NodeKind.APPROVAL` |
| **No-op** | `type: noop` | Maps to `NodeKind.NOOP` (checkpoint) |

**Default:** if `tool` is set, kind = `tool_call`. If only `type` is set, use typed handler.

---

## Variable Interpolation

| Syntax | Scope | Example |
|--------|-------|---------|
| `$variables.key` | Journey | `$variables.s3_prefix` |
| `$stage_id.step_id` | Cross-step within execution | `$entity_resolution.opportunities` |
| `$item.field` | `foreach` iterator | `$item.Opportunity_ID` |
| `$env.VAR` | Engine config | `$env.AWS_REGION` |
| `{secret_ref: path}` | Resolved at dispatch | credentials |

Resolution order: step params → stage outputs → journey variables → env.

---

## Control Flow

### Sequential (default)

Steps run in list order; step *N+1* depends on step *N* unless `depends_on` overrides.

### Parallel

```yaml
- id: parallel_fetch
  parallel: true
  steps:
    - { id: fetch_orders, tool: query_virtual_entity, ... }
    - { id: fetch_invoices, tool: query_virtual_entity, ... }
```

Compiled to `ExecutionNode.can_parallel = true` with shared dependency frontier.

### Foreach

```yaml
foreach: "$opportunities.items"
params:
  id: "$item.Id"
```

Compiler expands to **dynamic subgraph** (bounded by `max_foreach_items: 1000`) OR
loops inside a single tool invocation when tool supports batch (tool-specific).

### Condition

```yaml
condition: "$previous_step.count > 0"
```

Skipped steps → `NodeStatus.SKIPPED`.

### Stage DAG

```yaml
stages:
  - id: stage_a
    steps: [...]
  - id: stage_b
    depends_on: [stage_a]
    steps: [...]
```

Full journey execution runs stages respecting DAG. Single-stage submit runs one stage only.

---

## Retry, Timeout, Approval

Per-step overrides inherit from `spec.defaults`:

```yaml
retry:
  max_attempts: 3
  initial_backoff_s: 1
  max_backoff_s: 60
  backoff_multiplier: 2
  jitter: true
  retryable_errors: [TIMEOUT, THROTTLED]

timeout_s: 120

requires_approval: false
risk_class: read                      # read | write | destructive
```

If `risk_class: write|destructive` and `requires_approval: true`, compiler inserts
an `APPROVAL` node before the tool node (same rule as nexus-sre ExecutionGraph).

---

## Verification

```yaml
verification:
  - check_id: row_count_positive
    expression: "$result.count > 0"
    timeout_s: 30
    on_failure: abort                 # abort | warn | ignore
```

Maps to `NodeVerification` in ExecutionGraph.

---

## Rollback

```yaml
rollback:
  strategy: explicit                  # none | explicit | best_effort
  steps:
    - tool: delete_s3_prefix
      params:
        path: "$variables.s3_prefix/exceptions/"
```

Maps to nexus-sre `RollbackStrategy`.

---

## Compilation to ExecutionGraph

The **DSL Compiler** (`journeys/compiler.py`) transforms Journey DSL → frozen `ExecutionGraph`:

1. Validate tool names exist in registry (optional strict mode)
2. Expand `foreach` / `parallel` into nodes (with bounds)
3. Insert approval nodes per policy
4. Wire `depends_on` edges
5. Compute `content_sha256`
6. Persist graph snapshot on Execution record

```python
graph = JourneyCompiler().compile(journey_def, tenant_id=..., trace_id=...)
```

---

## Validation Rules

1. `metadata.id` matches `^[a-z0-9-]+$`
2. `stages` non-empty; each stage has ≥1 step
3. `step.id` unique within journey
4. `tool` names must match `^[a-z][a-z0-9_]*$`
5. `depends_on` references must resolve (no cycles)
6. `foreach` source must reference a prior step output binding
7. Total compiled nodes ≤ 200 (nexus-sre limit)
8. `schedule` required when `trigger: schedule`

---

## Storage Format

| Artifact | Store | Key pattern |
|----------|-------|-------------|
| Journey definition | DynamoDB | `JOURNEY#{id}` / `VERSION#{version}` |
| Latest pointer | DynamoDB | `JOURNEY#{id}` / `META#latest` |
| Compiled graph | DynamoDB | `EXECUTION#{id}` / `GRAPH#snapshot` |
| Large YAML | S3 | `s3://.../journeys/{id}/v{version}.yaml` |

---

## Compatibility with Existing YAML

Existing plugin journey YAML (`JourneyDefinition` in `plugin_models.py`) maps 1:1:

| Plugin field | DSL field |
|--------------|-----------|
| `JourneyDefinition.name` | `metadata.id` |
| `JourneyDefinition.steps` | Flatten into single default stage OR `stages[0].steps` |
| `JourneyStep.tool` | `step.tool` |
| `JourneyStep.foreach` | `step.foreach` |
| `JourneyStep.type` | `step.type` |

Migration CLI:

```bash
nexus-ai-engine journeys migrate-plugin-yaml --input plugin/journeys/ --output examples/journeys/
```

---

## JSON Schema

Generated to `schemas/journey-dsl-v1.json` from Pydantic models in
`contracts/journey_dsl.py` (to be implemented).

---

## Example: Minimal Journey

```yaml
apiVersion: nexus.ai/v1
kind: Journey
metadata:
  id: hello-tool
  version: 1
spec:
  display_name: Hello Tool
  stages:
    - id: main
      steps:
        - id: ping
          tool: query_virtual_entity
          params:
            entity: HealthCheck
            limit: 1
```

Submit:

```bash
curl -X POST /api/v1/executions \
  -H 'Content-Type: application/json' \
  -d '{"journey_id":"hello-tool","mode":"full"}'
```
