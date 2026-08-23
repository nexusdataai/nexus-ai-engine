# Chapter 3 — Journey DSL Authoring

**Release:** v0.2.0-beta | **Sprint:** 4 | **UAT:** `docs/delivery/020-v0.2.0-beta-uat.md` (β-G1)

This chapter walks through authoring a Journey DSL document, validating it, compiling to an ExecutionGraph, and storing it via the REST API.

---

## Prerequisites

```bash
cd /opt/mycode/nexus/nexus-ai-engine
make install-venv && source .venv/bin/activate
make serve   # http://localhost:8001 — use another port if 8001 is taken (e.g. --port 8010)
```

Sample DSL: `sdk/examples/journeys/order-to-cash.yaml`

Spec reference: `docs/spec/010-journey-dsl.md`

---

## 1. YAML structure

A valid Journey DSL document has this top-level shape:

```yaml
apiVersion: nexus.ai/v1
kind: Journey
metadata:
  id: order-to-cash-monitor    # ^[a-z0-9-]+$
  version: 1                   # monotonic integer
  labels:
    domain: finance
spec:
  display_name: Order-to-Cash Monitor
  trigger: manual              # manual | schedule | event
  stages:
    - id: entity_resolution
      steps:
        - id: fetch_opportunities
          tool: query_virtual_entity
          params:
            entity: Opportunity
            limit: 500
```

Key rules:

| Rule | Detail |
|------|--------|
| Stage IDs | `^[a-z][a-z0-9_]*$` |
| Step IDs | Unique across the entire journey |
| Tool names | `^[a-z][a-z0-9_]*$` when `tool` is set |
| Stages | At least one stage, each with ≥1 step |
| Schedule | Required when `trigger: schedule` |

Open the full O2C sample:

```bash
less sdk/examples/journeys/order-to-cash.yaml
```

---

## 2. Validate (without storing)

Send the YAML to the validate endpoint. Invalid documents return structured errors; valid ones return `"valid": true`.

```bash
curl -s -X POST http://localhost:8001/api/v1/journeys/validate \
  -H 'Content-Type: application/yaml' \
  --data-binary @sdk/examples/journeys/order-to-cash.yaml | jq .
```

Expected (valid):

```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

Test rejection (β-J1):

```bash
curl -s -X POST http://localhost:8001/api/v1/journeys/validate \
  -H 'Content-Type: application/json' \
  -d '{"apiVersion":"nexus.ai/v1","kind":"Journey","metadata":{"id":"bad id","version":1},"spec":{"display_name":"x","stages":[]}}' | jq .
```

---

## 3. Import (create versioned journey)

```bash
curl -s -X POST http://localhost:8001/api/v1/journeys/import \
  -H 'Content-Type: application/yaml' \
  --data-binary @sdk/examples/journeys/order-to-cash.yaml | jq .metadata
```

List versions:

```bash
curl -s http://localhost:8001/api/v1/journeys/order-to-cash-monitor/versions
# [1]
```

Re-importing the same id+version returns **409** (published versions are immutable).

---

## 4. Compile to ExecutionGraph

After import, compile to the nexus-sre ExecutionGraph contract:

```bash
curl -s -X POST http://localhost:8001/api/v1/journeys/order-to-cash-monitor/compile | jq '{node_count: (.nodes | length), kinds: [.nodes[].kind], content_sha256}'
```

Expected: multiple `tool_call` nodes, optional `approval` node for write steps, and a `content_sha256` hash.

---

## 5. Export YAML round-trip

```bash
curl -s http://localhost:8001/api/v1/journeys/order-to-cash-monitor/export | jq -r .yaml > /tmp/exported.yaml
curl -s -X POST http://localhost:8001/api/v1/journeys/validate \
  -H 'Content-Type: application/yaml' \
  --data-binary @/tmp/exported.yaml | jq .valid
# true
```

---

## 6. Migrate legacy plugin YAML

Convert plugin-style journeys (`name` + `stage.steps`) to DSL v1:

```bash
python scripts/migrate-plugin-yaml.py \
  --input sdk/examples/journeys/hello.yaml \
  --dry-run

python scripts/migrate-plugin-yaml.py \
  --input sdk/examples/journeys/hello.yaml \
  --output /tmp/migrated/
```

---

## 7. Automated tests

```bash
pytest tests/unit/test_journey_dsl_models.py \
       tests/unit/test_journey_validator.py \
       tests/unit/test_dsl_journey_store.py \
       tests/integration/test_journey_compiler.py \
       tests/integration/test_journey_dsl_api.py -q
```

---

## Related

- API spec: `docs/spec/060-api-specification.md`
- Compiler alignment: `docs/spec/090-nexus-sre-executor-alignment.md`
- Prior chapters: `01-getting-started.md`, `02-embedded-dev-ui.md`
