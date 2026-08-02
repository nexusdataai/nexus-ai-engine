# v0.2.0 GA — Staging UAT Results

**Image:** `298722972165.dkr.ecr.us-east-1.amazonaws.com/nexus-ai-engine-api:0.2.0-f0df16c`  
**Namespace:** `ai-engine-prod`  
**Date:** 2026-08-03

## Readiness

```json
{"ready":true,"version":"0.2.0","checks":{"engine":{"status":"ok"},"tool_registry":{"status":"ok","stages":7},"dynamodb":{"status":"ok","journeys_table":"ai-engine-journeys-prod","executions_table":"ai-engine-executions-prod"}}}
```

## P0 Scenarios

| ID | Scenario | Result |
|----|----------|--------|
| v020-P2 | POST /executions submits journey | PASS |
| v020-P3 | GET /executions/{id} shows progress | PASS |
| v020-P4 | SSE stream delivers events < 5s | PASS |
| v020-P5 | Cancel lifecycle | PASS |

Evidence: `staging-uat.log`, `health.json`, `readiness.json`

## Infrastructure

- CloudFormation stack `ai-engine-storage-prod` provisioned
- SSM `/ai-engine/prod/*` seeded
- IRSA `ai-engine-role` bound to `ai-engine-prod/ai-engine-role-sa`
