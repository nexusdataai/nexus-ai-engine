# Chapter 6 — Monitoring Executions

**Release:** v0.2.0 | **Sprint:** 10 | **UAT:** `docs/delivery/050-v0.2.0-uat.md`

This chapter walks through submitting a journey execution, watching live progress over SSE, and using lifecycle controls (pause, resume, cancel).

## Prerequisites

- Nexus AI Engine v0.2.0+ deployed with DynamoDB executions table provisioned
- A journey imported via the DSL API (`POST /api/v1/journeys/import`)
- `curl` or any HTTP client; optional MCP client for `execution_tool`

## 1. Import a journey

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/journeys/import \
  -H 'Content-Type: application/yaml' \
  --data-binary @examples/journeys/order-to-cash.yaml
```

Note the `metadata.id` (e.g. `order-to-cash-monitor`).

## 2. Submit an execution

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/executions/ \
  -H 'Content-Type: application/json' \
  -d '{"journey_id":"order-to-cash-monitor","mode":"full"}'
```

Response (`202 Accepted`):

```json
{
  "execution_id": "...",
  "status": "PENDING",
  "journey_id": "order-to-cash-monitor",
  "links": {
    "self": "/api/v1/executions/{id}",
    "stream": "/api/v1/executions/{id}/stream",
    "graph": "/api/v1/executions/{id}/graph"
  }
}
```

## 3. Poll status

```bash
curl -sS http://127.0.0.1:8000/api/v1/executions/{execution_id}
```

Fields to watch: `status`, `revision`, `nodes`.

## 4. Stream live events (SSE)

```bash
curl -N http://127.0.0.1:8000/api/v1/executions/{execution_id}/stream
```

Events include `execution.submitted`, `execution.tick`, and terminal transitions. Keepalive comments arrive every ~20s when idle.

Browser example:

```javascript
const es = new EventSource(`/api/v1/executions/${executionId}/stream`);
es.addEventListener('execution.tick', (e) => console.log(JSON.parse(e.data)));
```

## 5. Lifecycle controls

| Action | Endpoint |
|--------|----------|
| Pause | `POST /api/v1/executions/{id}/pause` |
| Resume | `POST /api/v1/executions/{id}/resume` |
| Cancel | `POST /api/v1/executions/{id}/cancel` |

Cancel returns `409` if the execution is already terminal.

## 6. MCP — execution_tool

```json
{
  "action": "submit",
  "journey_id": "order-to-cash-monitor"
}
```

Other actions: `get`, `list`, `cancel`.

## 7. Readiness and persistence

`/readiness` reports DynamoDB journeys + executions tables when the production engine is wired. Execution state is persisted to `ai-engine-executions-{env}`; logs/reports land in S3 buckets configured via SSM.

After a worker pod restart, re-fetching an execution reloads state from DynamoDB and resumes the tick loop.

## 8. Concurrency limits

Global concurrent executions are capped by `max_concurrent_jobs` in engine config (default 10). Per-journey limits can be set on submit when supported by the journey definition.

When limits are exceeded, submit returns `429 Too Many Requests`.
