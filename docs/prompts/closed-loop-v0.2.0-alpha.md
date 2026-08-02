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

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine`
- Deployer: `/opt/mycode/nexus/nexus-deployer`

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
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./bump-version.sh ai-engine-api patch --dry-run
# If dev cluster available:
./package-images.sh --only-ai-engine-api
./create-ecr-images.sh ai-engine-api
./app-rollout.sh --capability ai-engine --env dev
kubectl get pods -n ai-engine-dev
kubectl port-forward -n ai-engine-dev svc/nexus-ai-engine-api 8001:8000
# Re-run Layer 2 + Playwright against port-forward URL
```

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
| `deploy-dev` | Pods Ready in dev namespace; smoke passes via port-forward |
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
- [ ] Dev deploy verified OR documented blocker with my approval

### How to start

1. Read the build plan and list todos still `pending`.
2. Start with **`contracts`** only.
3. After each task, show: **Task ID → PASS/FAIL → next task**.

Begin now with task `contracts`. Do not batch multiple todos in one turn unless I ask.

---

## Resume prompt (after a break)

```markdown
Continue the closed-loop v0.2.0-alpha build agent for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md

Follow: /opt/mycode/nexus/nexus-ai-engine/docs/prompts/closed-loop-v0.2.0-alpha.md

Rules: one pending todo at a time; layered verify (pytest → curl → Playwright → UAT); mark todos completed only when green; update UAT matrix and user guide as you go.

Read the build plan frontmatter for the first todo still `pending`, implement it, run verification, then stop and report PASS/FAIL before the next todo.
```

---

## Related

- Build plan: `docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md`
- Planning index: `docs/prompts/planning.md`
- UAT: `docs/delivery/010-v0.2.0-alpha-uat.md`
