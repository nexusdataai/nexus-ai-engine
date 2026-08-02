# Closed-loop build agent — Nexus AI Engine v1.0.0 Production GA

Use this prompt in **Cursor Agent mode**. Attach the build plan:
`@docs/dev-plan/build/v1.0.0-production-ga.plan.md`

**Prerequisite:** v0.3.0 Journey Studio must be **released** (SPA + Executions API in production use).

---

## Prompt (copy from here)

You are a **closed-loop delivery agent**. Execute **one build-plan task at a time** from the authoritative plan below. Do **not** start the next task until the current task's success criteria and verification gates pass.

This is **production GA**: Copilot decoupling, 500 concurrent load, security, Grafana, prod UAT, admin guides.

### Authoritative inputs (read first)

1. **Build plan:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v1.0.0-production-ga.plan.md`

2. **Release / sprint context:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/releases/v1.0.0-production-ga.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-13-backend-decoupling.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-14-uat-and-v1-0-0-ga.md`

3. **Specs:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/080-implementation-roadmap.md` (phase 10)  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/001-architecture.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/060-api-specification.md`

4. **UAT:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/delivery/070-v1.0.0-uat.md`

5. **User guide:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/08-admin-deployment.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/09-troubleshooting.md`

6. **Cross-repo (Copilot decoupling):**  
   `/opt/mycode/nexus/nexus-backend/` — AI Engine HTTP client, feature flag `AI_ENGINE_EXECUTION_ENABLED`

7. **kube-operator + prod deploy:**  
   `/opt/mycode/nexus/nexus-deployer/kube-operator/`  
   Rollout: `ai-engine-all` (API + UI + workers)  
   `/opt/mycode/nexus/nexus-deployer/aws-login/set-context.sh` (index **3**)

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine`
- Backend (Copilot): `/opt/mycode/nexus/nexus-backend`
- Deployer: `/opt/mycode/nexus/nexus-deployer`

### AWS + EKS context (prod verification)

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3 && source .active-env && ./set-context.sh --status
```

Prod UAT (`uat-execute`) runs on **production** or prod-like cluster — confirm with me before destructive load tests.

### Closed-loop rules (mandatory)

1. Todos **in file order**; one in flight.  
2. **No prod path** to `CopilotEngine.execute_plan` when flag on (v100-I2).  
3. Security (`pentest`, `mtls`) — remediate **sev1 only**; document sev2+ waivers.  
4. Load test (`load-500`) — fix blockers only; capture metrics in evidence.  
5. **No git commit/push** unless I explicitly ask.

### Per-task verification layers

**Layer 1 — Unit / integration**

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate
pytest tests/unit tests/integration -q
make test-integration
```

**Layer 2 — Copilot → Engine integration (nexus-backend)**

```bash
# After engine-client + copilot-decouple todos
# Verify POST /api/v1/executions called from Copilot with flag on
# Verify execute_plan path disabled in prod config
```

**Layer 3 — UAT-mapped verification**

| UAT ID | Verify |
|--------|--------|
| v100-I1 | Copilot submits to AI Engine (prod flag on) |
| v100-I2 | No prod `execute_plan` path |
| v100-I3 | O2C + supply-chain reference journeys prod run |
| v100-L1 | 500 concurrent load test PASS |
| v100-S1 | Pen test sev1 = 0 |
| v100-S2 | mTLS engine ↔ ontology |
| v100-O1 | Grafana dashboards live |
| v100-G1 | Ch.8 admin deployment walkthrough |
| v100-G2 | Ch.9 troubleshooting scenarios |

**Layer 4 — Observability (`grafana`, `alerts`)**

- Dashboards: executions, queue depth, tool/VDL latency, worker health  
- Alerts: failed executions, worker down, ontology circuit open  
- Evidence: dashboard URLs or export JSON in `docs/delivery/evidence/v1.0.0/`

**Layer 5 — Production deploy (`release-cut`)**

```bash
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./bump-version.sh ai-engine-api minor   # or patch per semver policy
./bump-version.sh ai-engine-ui minor
./package-images.sh --only-ai-engine-images
./create-ecr-images.sh --only-ai-engine-images
./app-rollout.sh --capability ai-engine --env prod --namespace ai-engine-prod ai-engine-all
kubectl get pods -n ai-engine-prod
```

**Layer 6 — Prod UAT + sign-off**

- `070-v1.0.0-uat.md` — P0 100%  
- PO / Security / SRE / QA sign-off table filled  
- Ch.8–9 complete (v100-G1, v100-G2)

### Task-specific success criteria

| Todo ID | Done when |
|---------|-----------|
| `engine-client` | nexus-backend HTTP client for POST `/executions` |
| `copilot-decouple` | Flag `AI_ENGINE_EXECUTION_ENABLED`; prod execute_plan deprecated |
| `grafana` | Dashboards deployed and linked |
| `alerts` | Alert rules firing on synthetic failure test |
| `mtls` | mTLS between AI Engine and ontology verified |
| `load-500` | 500 concurrent PASS; evidence log |
| `pentest` | Sev1 = 0 or documented exception |
| `ref-journeys` | O2C + supply-chain verified in prod |
| `uat-execute` | Prod UAT matrix signed off |
| `userguide-ch8` | Ch.8 admin deployment complete |
| `userguide-ch9` | Ch.9 troubleshooting complete |
| `release-cut` | VERSION = 1.0.0; tag; `ai-engine-all` prod rollout |

### Release exit criteria

- [ ] All todos completed  
- [ ] Copilot fully decoupled in prod  
- [ ] 500 concurrent load PASS  
- [ ] Pen test sev1 = 0  
- [ ] Grafana + alerts operational  
- [ ] Prod UAT signed (PO, Security, SRE, QA)  
- [ ] User guide Ch.8–9 complete  

### How to start

First `pending` todo. Confirm prod vs staging for each task before running load/security tests.

---

## Resume prompt

```markdown
Continue closed-loop v1.0.0 Production GA for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v1.0.0-production-ga.plan.md

Follow: docs/prompts/closed-loop-v1.0.0.md

Cross-repo: nexus-backend for copilot-decouple. Prod UAT on set-context index 3.

First pending todo → verify → PASS/FAIL. Confirm before load-500 or pentest on prod.
```

---

## Related

- Build plan: `docs/dev-plan/build/v1.0.0-production-ga.plan.md`
- UAT: `docs/delivery/070-v1.0.0-uat.md`
- Master plan phase 10: `docs/spec/080-implementation-roadmap.md`
- Prior: `docs/prompts/closed-loop-v0.3.0.md`
