# Chapter 4 — Executions API

**Release:** v0.2.0-rc1 | **Sprint:** 6 | **UAT:** `docs/delivery/030-v0.2.0-rc1-uat.md` (rc1-G1)

Submit and monitor **in-process** journey executions via `ExecutionManager` (no Temporal in rc1).

---

## Prerequisites

```bash
cd /opt/mycode/nexus/nexus-ai-engine
make install-venv && source .venv/bin/activate
make serve   # http://localhost:8001
```

Import a DSL journey first (Ch.3):

```bash
curl -s -X POST http://localhost:8001/api/v1/journeys/import \
  -H 'Content-Type: application/yaml' \
  --data-binary @sdk/examples/journeys/order-to-cash.yaml | jq .metadata.id
```

---

## 1. Submit execution

```bash
curl -s -X POST http://localhost:8001/api/v1/executions/ \
  -H 'Content-Type: application/json' \
  -d '{"journey_id":"order-to-cash-monitor","mode":"full","labels":{"triggered_by":"manual"}}' | jq .
```

Expected **202 Accepted**:

```json
{
  "execution_id": "...",
  "status": "PENDING",
  "journey_id": "order-to-cash-monitor",
  "links": {
    "self": "/api/v1/executions/...",
    "stream": "/api/v1/executions/.../stream",
    "graph": "/api/v1/executions/.../graph",
    "nodes": "/api/v1/executions/.../nodes"
  }
}
```

The server runs the execution to completion in the background using the embedded mock tool registry.

---

## 2. Poll status

```bash
EXEC_ID="<from submit response>"
curl -s http://localhost:8001/api/v1/executions/$EXEC_ID | jq '{status, journey_id, revision}'
```

Terminal statuses: `succeeded`, `failed`, `cancelled`, `timed_out`.

---

## 3. Inspect node states

```bash
curl -s http://localhost:8001/api/v1/executions/$EXEC_ID/nodes | jq '[.[].status]' 
curl -s http://localhost:8001/api/v1/executions/$EXEC_ID/graph | jq '.nodes | length'
```

---

## 4. Cancel execution

```bash
curl -s -X POST http://localhost:8001/api/v1/executions/$EXEC_ID/cancel | jq .
```

Returns **409** if the execution is already terminal.

---

## 5. List executions

```bash
curl -s "http://localhost:8001/api/v1/executions/?journey_id=order-to-cash-monitor" | jq .
```

---

## 6. Pause / resume

```bash
curl -s -X POST http://localhost:8001/api/v1/executions/$EXEC_ID/pause | jq .
curl -s -X POST http://localhost:8001/api/v1/executions/$EXEC_ID/resume | jq .
```

---

## Architecture notes (rc1)

| Component | Role |
|-----------|------|
| `ExecutionManager` | Submit + tick loop |
| `EmbeddedToolRegistry` | Mock O2C tools in-process |
| `ToolDispatcher` | Dispatches `ToolRequest` → registry |
| `InMemoryEngine` | Holds `dsl_store` + `execution_manager` |

SSE stream (`/stream`) and DynamoDB persistence arrive in v0.2.0.

---

## Related

- Spec: `docs/spec/020-execution-engine.md`, `021-execution-state-machine.md`, `060-api-specification.md`
- Ch.3: `03-journey-dsl-authoring.md`
- UAT: `docs/delivery/030-v0.2.0-rc1-uat.md`
