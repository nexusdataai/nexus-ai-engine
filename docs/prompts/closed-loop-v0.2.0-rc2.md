# Closed-loop build agent — Nexus AI Engine v0.2.0-rc2 Tool Platform

Use this prompt in **Cursor Agent mode**. Attach the build plan:
`@docs/dev-plan/build/v0.2.0-rc2-tool-platform.plan.md`

**Prerequisites:** v0.2.0-beta **and** v0.2.0-rc1 must be **released** (rc1 ships ExecutionManager + ToolDispatcher; rc2 replaces mocks with real SDK + ontology HTTP).

---

## Prompt (copy from here)

You are a **closed-loop delivery agent**. Execute **one build-plan task at a time** from the authoritative plan below. Do **not** start the next task until the current task's success criteria and verification gates pass.

### Authoritative inputs (read first)

1. **Build plan:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-rc2-tool-platform.plan.md`

2. **Release / sprint context:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/releases/v0.2.0-rc2-tool-platform.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-07-tool-sdk-registry.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-08-uat-and-v0-2-0-rc2-ga.md`

3. **Specs:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/040-tool-registry-integration.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/041-ontology-data-plane-api.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/010-journey-dsl.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/090-nexus-sre-executor-alignment.md`

4. **UAT:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/delivery/040-v0.2.0-rc2-uat.md`

5. **User guide:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/05-tool-packages-ontology.md`

6. **Cross-repo (ontology APIs — nexus-backend):**  
   `/opt/mycode/nexus/nexus-backend/` (VDL + Connector promotion per spec 041)

7. **kube-operator + AWS context:**  
   `/opt/mycode/nexus/nexus-deployer/kube-operator/`  
   `/opt/mycode/nexus/nexus-deployer/aws-login/set-context.sh` (index **3**)

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine`
- Ontology backend: `/opt/mycode/nexus/nexus-backend`
- Deployer: `/opt/mycode/nexus/nexus-deployer`

### Architecture (locked — do not violate)

- **Compute in AI Engine** — tools run in engine workers  
- **Data in ontology** — VDL + Connector via HTTP only (no in-process VQ)

### AWS + EKS context

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3 && source .active-env && ./set-context.sh --status
```

Staging ontology must have O2C entity mappings for rc2-T2 / rc2-O1.

### Closed-loop rules (mandatory)

1. Process todos **in file order**; one task in flight.  
2. Mark todo `completed` only when all verification layers pass.  
3. Cross-repo tasks (`ontology-vdl`, `ontology-connector`) may require changes in **nexus-backend** — document both repos in verification log.  
4. Evidence per task in build plan **Verification log**.  
5. **No git commit/push** unless I explicitly ask.

### Per-task verification layers

**Layer 1 — Unit / contract**

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate
ruff check backend/src packages tests
pytest tests/unit tests/contracts -q
pytest tests/integration -q -k tool 2>/dev/null || true
```

**Layer 2 — API smoke**

```bash
make serve
curl -sf http://localhost:8001/api/v1/tools/ | jq .
curl -sf -X POST http://localhost:8001/api/v1/tool-packages \
  -H 'Content-Type: application/json' -d @examples/tool-packages/o2c/manifest.json
```

**Layer 3 — UAT-mapped tests**

| UAT ID | Verify |
|--------|--------|
| rc2-T1 | Publish tool package registers tools |
| rc2-T2 | O2C match tool queries staging VDL |
| rc2-T3 | Compiler strict mode rejects unknown tool |
| rc2-T4 | Connector invoke via SDK |
| rc2-T5 | VDL batch-query |
| rc2-O1 | Ontology `POST /api/v1/vdl/query` returns rows |
| rc2-G1 | User guide Ch.5 walkthrough |

**Layer 4 — Staging deploy**

```bash
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./bump-version.sh ai-engine-api patch
./package-images.sh --only-ai-engine-api
./create-ecr-images.sh --only-ai-engine-api
./app-rollout.sh --capability ai-engine --env prod --namespace ai-engine-prod ai-engine-api
```

Run `contract-tests` todo against **staging ontology** OpenAPI.

**Layer 5 — UAT execute**

- `docs/delivery/040-v0.2.0-rc2-uat.md` — P0 100%, P1 ≥90%  
- Evidence: `docs/delivery/evidence/v0.2.0-rc2/`

**Layer 6 — User guide Ch.5 (rc2-G1)**

### Task-specific success criteria

| Todo ID | Done when |
|---------|-----------|
| `tool-sdk` | `packages/nexus-tool-sdk` with VdlClient, ConnectorClient, ToolRuntime |
| `tool-base` | Tool base aligned with nexus-sre descriptor + `_dispatch` |
| `tool-registry` | ToolRegistry load/list/get |
| `publish-api` | `POST /api/v1/tool-packages` with manifest validation |
| `tools-o2c` | O2C package migrated; VDL over HTTP |
| `dispatcher-sdk` | ToolDispatcher creates ToolRuntime; forwards tenant headers |
| `compiler-strict` | `strict_tool_validation` against catalog |
| `ontology-vdl` | nexus-backend VDL query + batch-query promoted |
| `ontology-connector` | Unified connector invoke facade |
| `contract-tests` | SDK tests pass against staging ontology OpenAPI |
| `uat-execute` | rc2 UAT matrix signed off |
| `userguide-ch5` | Ch.5 complete; rc2-G1 PASS |
| `release-cut` | VERSION = 0.2.0-rc2; tag |

### Release exit criteria

- [ ] All todos completed  
- [ ] Ontology VDL + Connector live on staging  
- [ ] O2C tool package publishes and executes against staging VDL  
- [ ] UAT P0 100%  
- [ ] Ch.5 user guide complete  

### How to start

Begin with the first `pending` todo in the build plan. One task per turn unless I ask otherwise.

---

## Resume prompt

```markdown
Continue closed-loop v0.2.0-rc2 for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-rc2-tool-platform.plan.md

Follow: docs/prompts/closed-loop-v0.2.0-rc2.md

Prerequisites: rc1 ExecutionManager must exist. Cross-repo: nexus-backend for ontology-vdl/connector todos.

Cluster: ./set-context.sh 3 && source .active-env

First pending todo only → verify → report PASS/FAIL.
```

---

## Related

- Build plan: `docs/dev-plan/build/v0.2.0-rc2-tool-platform.plan.md`
- Prior: `docs/prompts/closed-loop-v0.2.0-beta.md`, rc1 build plan `v0.2.0-rc1-execution-engine.plan.md`
- UAT: `docs/delivery/040-v0.2.0-rc2-uat.md`
