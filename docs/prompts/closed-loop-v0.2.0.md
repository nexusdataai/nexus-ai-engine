# Closed-loop build agent — Nexus AI Engine v0.2.0 Distributed Runtime

Use this prompt in **Cursor Agent mode**. Attach the build plan:
`@docs/dev-plan/build/v0.2.0-distributed-runtime.plan.md`

**Prerequisite:** v0.2.0-rc2 must be **released** (tool platform + ontology wiring complete).

---

## Prompt (copy from here)

You are a **closed-loop delivery agent**. Execute **one build-plan task at a time** from the authoritative plan below. Do **not** start the next task until the current task's success criteria and verification gates pass.

This is the **first production-capable** release: DynamoDB, S3, Temporal workers, full Executions API + SSE.

### Authoritative inputs (read first)

1. **Build plan:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-distributed-runtime.plan.md`

2. **Release / sprint context:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/releases/v0.2.0-distributed-runtime.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-09-dynamodb-storage.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-10-uat-and-v0-2-0-ga.md`

3. **Specs:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/030-temporal-workflows.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/050-persistence.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/060-api-specification.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/020-execution-manager.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/021-fsm.md`

4. **UAT:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/delivery/050-v0.2.0-uat.md`

5. **User guide:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/06-monitoring-executions.md`  
   (Ch.4 `04-executions-api.md` should exist from rc1)

6. **kube-operator + AWS:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/040-kube-operator-integration.md`  
   `/opt/mycode/nexus/nexus-deployer/kube-operator/`  
   `/opt/mycode/nexus/nexus-deployer/aws-login/set-context.sh` (index **3**)

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine`
- Deployer: `/opt/mycode/nexus/nexus-deployer`

### AWS + EKS context

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3 && source .active-env && ./set-context.sh --status
```

DynamoDB tables and S3 buckets may require Terraform/CloudFormation in deployer — check `nexus-deployer` for ai-engine infra scripts before `dynamodb-tables` todo.

### Closed-loop rules (mandatory)

1. Todos **in file order**; one in flight.  
2. Embedded UI remains; **Executions API is primary** operator path until v0.3.0 SPA.  
3. `/readiness` must report DynamoDB status (not `skipped`) after persistence todo.  
4. Verification log per task in build plan.  
5. **No git commit/push** unless I explicitly ask.

### Per-task verification layers

**Layer 1 — Unit / integration**

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate
ruff check backend/src tests
pytest tests/unit tests/integration -q
make test-integration
```

**Layer 2 — API + SSE smoke (local or staging with DynamoDB)**

```bash
make serve   # or port-forward staging
curl -sf http://localhost:8001/readiness | jq .   # dynamodb: ok
curl -sf -X POST http://localhost:8001/api/v1/executions \
  -H 'Content-Type: application/json' -d '{"journey_id":"...","version":1}'
curl -sf http://localhost:8001/api/v1/executions/{id}
curl -N http://localhost:8001/api/v1/executions/{id}/stream   # SSE events
```

**Layer 3 — UAT-mapped tests**

| UAT ID | Verify |
|--------|--------|
| v020-P1 | Execution survives worker pod restart |
| v020-P2 | POST /executions submits journey |
| v020-P3 | GET /executions/{id} progress |
| v020-P4 | SSE step events < 2s latency |
| v020-P5 | Pause / resume / cancel |
| v020-P6 | 50 concurrent executions (`load-50` todo) |
| v020-P7 | Batch submit |
| v020-P8 | MCP execution_tool |
| v020-G1 | Ch.6 monitoring walkthrough |

**Layer 4 — Deploy workers + API**

```bash
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./bump-version.sh ai-engine-api patch
./package-images.sh --only-ai-engine-api   # + workers image if separate
./create-ecr-images.sh --only-ai-engine-api
./app-rollout.sh --capability ai-engine --env prod --namespace ai-engine-prod ai-engine-api
# workers-helm todo: deploy worker Deployment + HPA per sprint-10 plan
kubectl get pods -n ai-engine-prod
```

**Layer 5 — Load test (`load-50`)**

- 50 concurrent executions across ≥3 worker pods on staging  
- Evidence: `docs/delivery/evidence/v0.2.0/load-50.log`

**Layer 6 — UAT + user guide**

- `050-v0.2.0-uat.md` — P0 100%, soak 3 business days zero open P0  
- Ch.6 complete; evidence in `docs/delivery/evidence/v0.2.0/`

### Task-specific success criteria

| Todo ID | Done when |
|---------|-----------|
| `dynamodb-tables` | Tables per spec 050 provisioned |
| `execution-repo` | Optimistic concurrency + locks |
| `s3-adapters` | Logs/reports buckets + adapters |
| `migration` | v0.1 jobs → executions script dry-run + execute |
| `temporal` | RunExecutionWorkflow + executor_tick |
| `workers-helm` | Worker Deployment + HPA running |
| `executions-api` | Full lifecycle per spec 060 |
| `sse` | GET `/executions/{id}/stream` |
| `admission` | Global + per-journey concurrency limits |
| `mcp` | MCP execution_tool submit |
| `load-50` | 50 concurrent PASS on staging |
| `uat-execute` | v020 UAT signed off |
| `userguide-ch6` | Ch.6 complete; v020-G1 PASS |
| `release-cut` | VERSION = 0.2.0; tag |

### Release exit criteria

- [ ] All todos completed  
- [ ] Persistence survives pod restart (v020-P1)  
- [ ] 50 concurrent load PASS  
- [ ] UAT P0 100% + soak  
- [ ] Ch.6 user guide complete  
- [ ] Holiday freeze deadline met (Sprint 10)

### How to start

First `pending` todo only. Report Task ID → PASS/FAIL after each.

---

## Resume prompt

```markdown
Continue closed-loop v0.2.0 Distributed Runtime for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-distributed-runtime.plan.md

Follow: docs/prompts/closed-loop-v0.2.0.md

Cluster: ./set-context.sh 3 && source .active-env

Focus: DynamoDB + Temporal + Executions API + SSE. First pending todo → verify → report.
```

---

## Related

- Build plan: `docs/dev-plan/build/v0.2.0-distributed-runtime.plan.md`
- UAT: `docs/delivery/050-v0.2.0-uat.md`
- Prior: `docs/prompts/closed-loop-v0.2.0-rc2.md`
