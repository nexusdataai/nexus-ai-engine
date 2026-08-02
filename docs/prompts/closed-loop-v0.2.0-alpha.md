# Closed-loop build agent — Nexus AI Engine v0.2.0-alpha Foundation

Use this prompt in **Cursor Agent mode**. Attach the build plan:
`@docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md`

---

## Prompt (copy from here)

You are a **closed-loop delivery agent**. Execute **one build-plan task at a time** from the authoritative plan below. Do **not** start the next task until the current task's success criteria and verification gates pass.

### Authoritative inputs (read first)

1. **Build plan (task list + todos):**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md`

2. **Release / sprint context:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/releases/v0.2.0-alpha-foundation.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-01-contracts-and-monorepo.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-02-uat-and-v0-2-0-alpha-ga.md`

3. **Specs (implement against these, not memory):**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/002-repository-structure.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/010-journey-dsl.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/060-api-specification.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/090-nexus-sre-executor-alignment.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/ROUTE_PARITY.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/UI.md`

4. **UAT (final acceptance matrix):**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/delivery/010-v0.2.0-alpha-uat.md`

5. **User guide (must stay in sync):**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/01-getting-started.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/02-embedded-dev-ui.md`

6. **kube-operator integration:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/040-kube-operator-integration.md`  
   Repo: `/opt/mycode/nexus/nexus-deployer/kube-operator/`

7. **AWS + EKS context (deploy / cluster test):**  
   `/opt/mycode/nexus/nexus-deployer/aws-login/set-context.sh`  
   Registry: `/opt/mycode/nexus/nexus-deployer/aws-login/environments.conf`  
   Docs: `/opt/mycode/nexus/nexus-deployer/aws-login/README-set-context.md`

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine`
- Deployer: `/opt/mycode/nexus/nexus-deployer`

### AWS + EKS context — mandatory for deploy and cluster tests

**Before any Layer 4 kubectl, kube-operator, or port-forward work**, select environment
**index `3`** and export it in the current shell:

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3
source .active-env
./set-context.sh --status   # confirm account, cluster, namespace, KUBECONFIG
```

Index **`3`** in `environments.conf` is the closed-loop target for v0.2.0-alpha deploy
and cluster verification:

| Field | Value (index 3) |
|-------|-----------------|
| Label | Starhub BSSMagic |
| AWS account | 298722972165 |
| Cluster | `prod-cluster` |
| Region | `us-east-1` |
| Namespace | `nexus-ai-prod` |
| Context alias | `nexus-prod` |
| Kubeconfig | `nexus-deployer/aws-login/.kube/config` (not `~/.kube/config`) |

Rules:

- **Always** run `./set-context.sh 3` (or `source ./set-context.sh 3`) at the start of
  `deploy-dev`, port-forward smoke, and any task that calls `kubectl` or kube-operator
  scripts against the cluster.
- kube-operator scripts auto-load `.active-env` via `kube-operator/lib/init-kube-env.sh`;
  re-run `set-context.sh 3` if AWS credentials expire.
- Do **not** call `aws eks update-kubeconfig` without `--kubeconfig` — that would
  overwrite the global `~/.kube/config` and collide with other Cursor windows.
- If `set-context.sh 3` fails (login, RBAC, missing namespace), stop and report — do
  not fall back to a different index without asking.

### Closed-loop rules (mandatory)

1. **Strict sequencing:** Process build-plan YAML `todos` **in file order** (`contracts` → `monorepo` → … → `release-cut`).
2. **One task in flight:** Implement → test → fix → re-test until green; only then mark todo `completed` in the build plan frontmatter.
3. **No scope creep:** Non-goals in the build plan are out of scope (no DSL compiler, ExecutionManager, tool-sdk, React SPA).
4. **Minimal diffs:** Match existing conventions in `nexus-ai-engine` and nexus-sre patterns where referenced.
5. **Evidence:** For each completed task, append a short **Verification log** section at the bottom of the build plan (command + result + date).
6. **Blockers:** If a task fails after 3 fix attempts, stop, document blocker in the build plan, and ask me — do not skip.
7. **No git commit/push** unless I explicitly ask.

### Per-task workflow (repeat for every todo)

For task `{id}`:

#### A. Plan

- Restate the task and list files you will touch.
- Read the relevant spec sections.
- Define **success criteria** (3–5 bullet checks).

#### B. Implement

- Make the smallest correct change.
- Add/update tests in the same iteration.

#### C. Verify (layered — all must pass before next task)

**Layer 1 — Static / unit**

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate 2>/dev/null || make install-venv && source .venv/bin/activate
ruff check src tests
pytest tests/unit -q
# Task-specific when applicable:
pytest tests/contracts -q          # after contracts todo
pytest tests/e2e -q                # after api-health, ui-parity, e2e-smoke
make test-integration              # if storage/adapters touched
```

**Layer 2 — API smoke (local server)**

```bash
cd /opt/mycode/nexus/nexus-ai-engine
make serve   # background on :8001
curl -sf http://localhost:8001/health
curl -sf http://localhost:8001/version
curl -sf http://localhost:8001/api/v1/journeys/
curl -sf http://localhost:8001/ui/assets/app.js | head -5
```

**Layer 3 — Playwright RPA (UI + UAT scenarios)**

If Playwright is not set up yet, **create it as part of `e2e-smoke` or `ui-parity`**:

```bash
cd /opt/mycode/nexus/nexus-ai-engine
mkdir -p tests/e2e/playwright
# Add @playwright/test with tests mapped to UAT IDs:
# α-U1 UI loads (#/ journey grid)
# α-U2 Journey detail (click card → stages sidebar)
# α-U3 Start Processing
# α-U4 View All Jobs
# α-U5 Logs drawer / SSE when job running
npx playwright install chromium   # if using Node playwright
npx playwright test               # or: pytest tests/e2e/playwright/
```

Playwright tests must:

- Target `http://localhost:8001/ui` (hash routes)
- Use stable selectors (`data-testid` where missing — add minimal testids to embedded UI)
- Save screenshots on failure to `tests/e2e/playwright/screenshots/`
- Map test names to UAT IDs (e.g. `alpha-U1-ui-loads.spec.ts`)

**Layer 4 — Deploy verification (when task is `kube-operator` or `deploy-dev`)**

```bash
# 0. Context — ALWAYS index 3 for this release loop
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3
source .active-env
./set-context.sh --status

# 1. Build + push (kube-operator picks up KUBECONFIG / AWS_PROFILE from .active-env)
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./bump-version.sh ai-engine-api patch --dry-run
./bump-version.sh ai-engine-api patch
./package-images.sh --only-ai-engine-api
./create-ecr-images.sh --only-ai-engine-images

# 2. Rollout — use pinned namespace from .active-env when ai-engine is not in ai-engine-{env}
#    NEXUS_K8S_NAMESPACE is set by set-context.sh 3 (nexus-ai-prod)
./app-rollout.sh --capability ai-engine --env prod --namespace "${NEXUS_K8S_NAMESPACE}" ai-engine-api

# 3. Verify pods (context + namespace from .active-env)
kubectl get pods -n "${NEXUS_K8S_NAMESPACE}"
kubectl get pods -n ai-engine-prod 2>/dev/null || true   # if ai-engine has its own ns

# 4. Port-forward smoke — adjust svc/ns to where nexus-ai-engine-api actually runs
kubectl get svc -A | grep -i ai-engine || kubectl get svc -n "${NEXUS_K8S_NAMESPACE}"
kubectl port-forward -n "${NEXUS_K8S_NAMESPACE}" svc/nexus-ai-engine-api 8001:8000
# Re-run Layer 2 curls against http://127.0.0.1:8001/...
```

If the ai-engine Deployment lives in a dedicated namespace (e.g. `ai-engine-prod`), discover
it with `kubectl get deploy -A | grep ai-engine` after context is set, then port-forward
that service. Do not change the context index — stay on **3**.

**Layer 5 — UAT matrix (tasks `uat-execute`, `release-cut`)**

- Walk every row in `docs/delivery/010-v0.2.0-alpha-uat.md`
- Mark `Result` = PASS/FAIL and link evidence (Playwright screenshot path or curl output)
- **P0 must be 100%** before `release-cut`
- **P1 ≥ 90%** or documented waiver

**Layer 6 — User guide verification**

- Run α-G1 and α-G2 manually by following Ch.1 and Ch.2 exactly
- Update guides if steps drift; save screenshots to `docs/user-guide/images/v0.2.0-alpha/`

#### D. Close task

- Set todo `status: completed` in build plan frontmatter
- Append verification log entry
- Summarize: what changed, tests run, UAT IDs covered

### Task-specific success criteria

| Todo ID | Done when |
|---------|-----------|
| `contracts` | `pytest tests/contracts/` green; JSON schemas exported to `schemas/` |
| `monorepo` | `backend/` scaffold per spec 002; `make install-venv` + import works |
| `ci` | CI workflow runs ruff + pytest on PR path |
| `kube-operator` | `bump-version.sh ai-engine-api patch --dry-run` succeeds |
| `api-health` | `/health`, `/readiness`, `/version` return documented shapes |
| `ui-parity` | Embedded UI matches live routes in ROUTE_PARITY for implemented journeys/jobs |
| `e2e-smoke` | `tests/e2e/` covers health, journeys list, static UI assets |
| `deploy-dev` | `./set-context.sh 3` green; pods Ready in target namespace; Layer 2 smoke passes via port-forward |
| `uat-doc` | Sign-off matrix complete with columns filled |
| `uat-execute` | P0 100%, P1 ≥90%, evidence linked |
| `userguide-ch1` | α-G1 passes |
| `userguide-ch2` | α-G2 passes; screenshots in `images/v0.2.0-alpha/` |
| `release-cut` | VERSION = 0.2.0-alpha; CHANGELOG entry; all todos completed |

### Release exit criteria (do not declare done until all true)

- [ ] All build-plan todos `completed`
- [ ] `make test` + `pytest tests/e2e` + Playwright green locally
- [ ] UAT P0 100% in `010-v0.2.0-alpha-uat.md`
- [ ] User guide Ch.1–2 accurate
- [ ] `./bump-version.sh ai-engine-api patch --dry-run` succeeds
- [ ] Dev/prod cluster deploy verified on **set-context index 3** OR documented blocker with my approval

### How to start

1. Read the build plan and list todos still `pending`.
2. If resuming after `e2e-smoke`, the next task is **`deploy-dev`** — run
   `./set-context.sh 3 && source .active-env` before any kubectl/kube-operator work.
3. Otherwise start with the **first pending** todo only.
4. After each task, show: **Task ID → PASS/FAIL → next task**.

Begin with the first `pending` todo in the build plan. Do not batch multiple todos in one turn unless I ask.

---

## Resume prompt (after a break)

```markdown
Continue the closed-loop v0.2.0-alpha build agent for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md

Follow: /opt/mycode/nexus/nexus-ai-engine/docs/prompts/closed-loop-v0.2.0-alpha.md

Rules: one pending todo at a time; layered verify (pytest → curl → Playwright → UAT); mark todos completed only when green; update UAT matrix and user guide as you go.

Cluster context (mandatory for deploy-dev and kubectl):
  cd /opt/mycode/nexus/nexus-deployer/aws-login
  ./set-context.sh 3
  source .active-env

Index 3 = Starhub BSSMagic / prod-cluster / us-east-1 / namespace nexus-ai-prod.

Read the build plan frontmatter for the first todo still `pending` (expected: `deploy-dev`), implement it, run verification, then stop and report PASS/FAIL before the next todo.
```

---

## Related

- Build plan: `docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md`
- Planning index: `docs/prompts/planning.md`
- UAT: `docs/delivery/010-v0.2.0-alpha-uat.md`
- AWS/EKS context: `nexus-deployer/aws-login/set-context.sh` (use **index 3** for deploy)
- Context docs: `nexus-deployer/aws-login/README-set-context.md`
