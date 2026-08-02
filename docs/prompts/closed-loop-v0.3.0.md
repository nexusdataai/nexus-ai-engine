# Closed-loop build agent — Nexus AI Engine v0.3.0 Journey Studio

Use this prompt in **Cursor Agent mode**. Attach the build plan:
`@docs/dev-plan/build/v0.3.0-journey-studio.plan.md`

**Prerequisite:** v0.2.0 Distributed Runtime must be **released** (Executions API + SSE live on staging/prod).

---

## Prompt (copy from here)

You are a **closed-loop delivery agent**. Execute **one build-plan task at a time** from the authoritative plan below. Do **not** start the next task until the current task's success criteria and verification gates pass.

This release ships the **React SPA Journey Studio** (production operator UI). Embedded dev UI at `/ui` remains for port-forward testing.

### Authoritative inputs (read first)

1. **Build plan:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.3.0-journey-studio.plan.md`

2. **Release / sprint context:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/releases/v0.3.0-journey-studio.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-11-frontend-shell.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/sprints/sprint-12-uat-and-v0-3-0-ga.md`

3. **Specs:**  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/070-journey-studio-ui.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/002-repository-structure.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/060-api-specification.md`  
   - `/opt/mycode/nexus/nexus-ai-engine/docs/spec/UI.md` (embedded UI — do not break)

4. **UAT:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/delivery/060-v0.3.0-uat.md`

5. **User guide:**  
   `/opt/mycode/nexus/nexus-ai-engine/docs/user-guide/07-journey-studio.md`  
   Screenshots: `docs/user-guide/images/v0.3.0/`

6. **UI reference (look & feel):**  
   - `/opt/mycode/nexus/nexus-sre/frontend/` — shell, sidebar, theme tokens  
   - `/opt/mycode/nexus/nexus-ui/` — shared shadcn patterns

7. **kube-operator (API + UI images):**  
   `/opt/mycode/nexus/nexus-deployer/kube-operator/`  
   Targets: `ai-engine-api`, `ai-engine-ui`  
   `/opt/mycode/nexus/nexus-deployer/aws-login/set-context.sh` (index **3**)

### Repo roots

- AI Engine: `/opt/mycode/nexus/nexus-ai-engine` (`frontend/` SPA)
- Deployer: `/opt/mycode/nexus/nexus-deployer`

### Closed-loop rules (mandatory)

1. Todos **in file order**; one in flight.  
2. SPA must use **nexus-sre / nexus-ui shell pattern** (left sidebar, header utilities, dark/light theme).  
3. **Regression:** v0.2.0 Executions API must still pass curl tests (UAT note).  
4. Playwright tests required for v030-U* scenarios.  
5. **No git commit/push** unless I explicitly ask.

### Per-task verification layers

**Layer 1 — Frontend static**

```bash
cd /opt/mycode/nexus/nexus-ai-engine/frontend
npm ci
npm run lint
npm run build
npm run test -- --run 2>/dev/null || true
```

**Layer 2 — Local dev smoke**

```bash
# Terminal 1: API
cd /opt/mycode/nexus/nexus-ai-engine && make serve

# Terminal 2: SPA dev proxy
cd frontend && npm run dev
# Open http://localhost:5173 (or configured port)
curl -sf http://localhost:8001/api/v1/executions?status=RUNNING
```

**Layer 3 — Playwright RPA (required)**

```bash
cd /opt/mycode/nexus/nexus-ai-engine/frontend
npx playwright install chromium
npx playwright test
```

Map specs to UAT:

| UAT ID | Playwright scenario |
|--------|---------------------|
| v030-U1 | Dashboard active execution count |
| v030-U2 | Submit journey from UI |
| v030-U3 | Live SSE updates execution graph |
| v030-U4 | Journey Studio validate DSL |
| v030-U5 | Tool picker lists published tools |
| v030-U6 | Tools catalog page |
| v030-U7 | Keyboard nav primary flows (a11y) |
| v030-U8 | Cognito login staging (if auth todo done) |
| v030-G1 | Ch.7 screenshots in `images/v0.3.0/` |

Save failures to `frontend/playwright/screenshots/`.

**Layer 4 — Deploy API + UI**

```bash
cd /opt/mycode/nexus/nexus-deployer/aws-login
./set-context.sh 3 && source .active-env

cd ../kube-operator
./bump-version.sh ai-engine-api patch
./bump-version.sh ai-engine-ui patch
./package-images.sh --only-ai-engine-images
./create-ecr-images.sh --only-ai-engine-images
./app-rollout.sh --capability ai-engine --env prod --namespace ai-engine-prod ai-engine-all
kubectl get pods -n ai-engine-prod
```

**Layer 5 — UAT execute**

- `060-v0.3.0-uat.md` — P0 100%, P1 ≥90%  
- Evidence: `docs/delivery/evidence/v0.3.0/`

**Layer 6 — User guide Ch.7 (v030-G1)**

- Screenshots captured during Playwright or manual UAT

### Task-specific success criteria

| Todo ID | Done when |
|---------|-----------|
| `frontend-scaffold` | Vite + React 18 + TS + Tailwind + TanStack Query per spec 070 |
| `app-shell` | Routes: `/`, `/journeys`, `/executions`, `/schedules`, `/tools` |
| `dashboard` | Widgets from GET `/executions?status=RUNNING` |
| `executions-monitor` | List + detail + EventSource SSE reconnect |
| `journey-studio` | 3-column: stages, DSL editor, validate, tool picker |
| `reactflow` | Live execution graph on detail page |
| `tools-catalog` | Read-only `/tools` from GET `/api/v1/tools` |
| `auth` | Cognito JWT via ingress headers (staging) |
| `kube-ui` | ai-engine-ui nginx image in kube-operator pipeline |
| `a11y` | AA on primary flows (v030-U7) |
| `uat-execute` | v030 UAT signed off |
| `userguide-ch7` | Ch.7 + screenshots; v030-G1 PASS |
| `release-cut` | VERSION = 0.3.0; tag |

### Release exit criteria

- [ ] All todos completed  
- [ ] SPA deployed via `ai-engine-ui` image  
- [ ] Playwright green  
- [ ] Executions API regression curl tests pass  
- [ ] UAT P0 100%  
- [ ] Ch.7 with screenshots  

### How to start

First `pending` todo. One task per turn.

---

## Resume prompt

```markdown
Continue closed-loop v0.3.0 Journey Studio for:
/opt/mycode/nexus/nexus-ai-engine/docs/dev-plan/build/v0.3.0-journey-studio.plan.md

Follow: docs/prompts/closed-loop-v0.3.0.md

UI reference: nexus-sre + nexus-ui shell/theme. Playwright required for v030-U*.

Deploy: ai-engine-api + ai-engine-ui via kube-operator (set-context.sh 3).

First pending todo → verify → PASS/FAIL.
```

---

## Related

- Build plan: `docs/dev-plan/build/v0.3.0-journey-studio.plan.md`
- UAT: `docs/delivery/060-v0.3.0-uat.md`
- Prior: `docs/prompts/closed-loop-v0.2.0.md`
