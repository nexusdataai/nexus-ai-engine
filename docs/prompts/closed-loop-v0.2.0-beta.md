# Closed-loop build agent — Nexus AI Engine v0.2.0-beta Journey DSL

Use this prompt in **Cursor Agent mode**. Attach the build plan:
`@docs/dev-plan/build/v0.2.0-beta-journey-dsl.plan.md`

**Prerequisite:** v0.2.0-alpha Foundation must be **released** (build plan todos completed, tag `0.2.0-alpha`).

---

## Prompt (copy from here)

You are a **closed-loop delivery agent**. Execute **one build-plan task at a time** from the authoritative plan below. Do **not** start the next task until the current task's success criteria and verification gates pass.

### Authoritative inputs (read first)

1. **Build plan (task list + todos):**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-beta-journey-dsl.plan.md`

2. **Release / sprint context:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/releases/v0.2.0-beta-journey-dsl.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-03-journey-dsl-models.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-04-uat-and-v0-2-0-beta-ga.md`

3. **Specs (implement against these, not memory):**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/010-journey-dsl.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/060-api-specification.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/090-nexus-sre-executor-alignment.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/002-repository-structure.md`

4. **UAT (final acceptance matrix):**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/delivery/020-v0.2.0-beta-uat.md`

5. **User guide (must stay in sync):**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/03-journey-dsl-authoring.md`

6. **kube-operator integration:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/040-kube-operator-integration.md`  
   Repo: `/opt/mycode/nexus/nexus-deployer/kube-operator/`

7. **AWS + EKS context:**  
   `/opt/mycode/nexus/nexus-deployer/aws-login/set-context.sh` (index **3**)

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine`
- Deployer: `/opt/mycode/nexus/nexus-deployer`

### AWS + EKS context — mandatory for deploy and cluster tests

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3
source .active-env
./set-context.sh --status
```

| Field | Value (index 3) |
|-------|-----------------|
| Label | Starhub BSSMagic |
| AWS account | 298722972165 |
| Cluster | `prod-cluster` |
| Region | `us-east-1` |
| Namespace | `nexus-ai-prod` |
| Context alias | `nexus-prod` |

Discover ai-engine Deployment namespace with `kubectl get deploy -A | grep ai-engine` after context is set (often `ai-engine-prod`).

### Closed-loop rules (mandatory)

1. **Strict sequencing:** Process build-plan YAML `todos` **in file order**.
2. **One task in flight:** Implement → test → fix → re-test until green; only then mark todo `completed` in the build plan frontmatter.
3. **No scope creep:** Non-goals in the release plan are out of scope (no ExecutionManager, Temporal, React SPA).
4. **Minimal diffs:** Match existing conventions in `nexus-ai-engine`.
5. **Evidence:** Append a **Verification log** row at the bottom of the build plan per completed task.
6. **Blockers:** Stop after 3 fix attempts; document blocker; ask me — do not skip.
7. **No git commit/push** unless I explicitly ask.

### Per-task workflow (repeat for every todo)

#### A. Plan — restate task, list files, read specs, define 3–5 success criteria

#### B. Implement — smallest correct change + tests

#### C. Verify (all layers must pass before next task)

**Layer 1 — Static / unit**

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate 2>/dev/null || make install-venv && source .venv/bin/activate
ruff check backend/src tests
pytest tests/unit tests/contracts -q
pytest tests/integration -q -k journey 2>/dev/null || true
```

**Layer 2 — API smoke (local server)**

```bash
make serve   # background :8001
curl -sf -X POST http://localhost:8001/api/v1/journeys/validate \
  -H 'Content-Type: application/json' -d @examples/journeys/order-to-cash.yaml
curl -sf http://localhost:8001/api/v1/journeys/
```

**Layer 3 — Playwright / integration RPA**

Map tests to UAT IDs:

- β-J1 validate rejects invalid DSL  
- β-J2 validate accepts O2C sample  
- β-J3 compiler → ExecutionGraph golden tests  
- β-J4 create journey + list versions  
- β-J5 version immutability  
- β-J6 export YAML round-trip  
- β-J7 migrate-plugin-yaml dry-run  

Prefer `pytest tests/integration/` + golden files under `examples/journeys/`; add Playwright only if UI badges are implemented.

**Layer 4 — Deploy (when applicable)**

```bash
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./bump-version.sh ai-engine-api patch
./package-images.sh --only-ai-engine-api
./create-ecr-images.sh --only-ai-engine-api
./app-rollout.sh --capability ai-engine --env prod --namespace ai-engine-prod ai-engine-api
kubectl port-forward -n ai-engine-prod svc/nexus-ai-engine-api 8001:8000
# Re-run Layer 2 against :8001
```

**Layer 5 — UAT matrix (`uat-execute`, `release-cut`)**

- Walk every row in `docs/delivery/020-v0.2.0-beta-uat.md`  
- **P0 100%**, **P1 ≥ 90%**  
- Evidence in `docs/delivery/evidence/v0.2.0-beta/`

**Layer 6 — User guide (β-G1)**

- Follow Ch.3 exactly; update if steps drift

#### D. Close task

- Set todo `status: completed` in build plan frontmatter  
- Append verification log entry  
- Summarize: Task ID → PASS/FAIL → next task

### Task-specific success criteria

| Todo ID | Done when |
|---------|-----------|
| `dsl-models` | Journey/Stage/Step models per spec 010; contract tests green |
| `validator` | Semantic validation; `POST /journeys/validate` returns structured errors |
| `compiler` | DSL → ExecutionGraph; golden tests for `examples/journeys/*.yaml` |
| `journey-service` | Versioned CRUD; published versions immutable |
| `journeys-api` | REST CRUD per spec 060 |
| `migrate-script` | `scripts/migrate-plugin-yaml.py --dry-run` succeeds on sample |
| `uat-doc` | Sign-off matrix complete in `020-v0.2.0-beta-uat.md` |
| `uat-execute` | P0 100%, P1 ≥90%, evidence linked |
| `userguide-ch3` | Ch.3 complete; β-G1 PASS |
| `release-cut` | VERSION = 0.2.0-beta; CHANGELOG; tag |

### Release exit criteria

- [ ] All build-plan todos `completed`
- [ ] `pytest tests/unit tests/contracts tests/integration` green
- [ ] UAT P0 100% in `020-v0.2.0-beta-uat.md`
- [ ] User guide Ch.3 accurate
- [ ] Cluster deploy verified on set-context index 3 OR documented blocker

### How to start

1. Read the build plan; list todos still `pending`.
2. Start with the **first pending** todo only.
3. After each task, show: **Task ID → PASS/FAIL → next task**.

Begin with the first `pending` todo. Do not batch multiple todos unless I ask.

---

## Resume prompt (after a break)

```markdown
Continue the closed-loop v0.2.0-beta build agent for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-beta-journey-dsl.plan.md

Follow: /opt/mycode/nexus/nexus-ai-engine/docs/prompts/closed-loop-v0.2.0-beta.md

Rules: one pending todo at a time; layered verify; mark todos completed only when green.

Cluster context:
  cd /opt/mycode/nexus/nexus-deployer/aws-login && ./set-context.sh 3 && source .active-env

Read the build plan frontmatter for the first todo still `pending`, implement it, verify, stop and report PASS/FAIL before the next todo.
```

---

## Related

- Build plan: `docs/dev-plan/build/v0.2.0-beta-journey-dsl.plan.md`
- Prior release: `docs/prompts/closed-loop-v0.2.0-alpha.md`
- Planning index: `docs/prompts/planning.md`
