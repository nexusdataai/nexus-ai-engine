# Embedded Journey Studio UI

The reference server ships a small React UI for browsing, creating, running,
cancelling, and inspecting journeys, jobs, schedules, and prompts. It is
designed to be reached via `kubectl port-forward` — no ingress, no auth.

## Access

### Local (make serve)

```bash
make serve
# then open:
open http://localhost:8001/ui
```

### Deployed pod

```bash
kubectl -n ai-engine port-forward svc/nexus-ai-engine 8000:8000
open http://localhost:8000/ui
```

## What you can do

- **Journeys tab** — list, search, filter, create, clone, delete the
  5 seeded journeys (order-to-cash, call-processing, demand-forecasting,
  inventory-optimization, supply-chain-risk).
- **Journey Studio** — per-journey stage sidebar; KPI row (total jobs,
  success rate, avg duration, calls processed); stage-level
  "Start Processing" button; steps list.
- **Job History** — table of past and running jobs with counters + duration
  + status. Cancel running jobs, retry failed ones. Row click opens a logs
  drawer.
- **Logs Drawer** — live SSE stream from the in-memory executor; shows
  tick-by-tick progress of the simulated step pipeline, then a terminal
  pill (`completed`, `failed`, or `cancelled`).
- **Schedules** — per-journey batch schedules with toggle / Run Now /
  delete. Also a top-level `#/schedules` view with schedules grouped by
  journey.
- **Prompts** — catalog of system prompts with version history + audit log;
  edit the content and save, or reset all to defaults.

## Architecture

```
Browser (http://localhost:8000)
  │
  │ (kubectl port-forward)
  ▼
FastAPI reference server (/ui + /api/v1/*)
  │
  ▼
InMemoryEngine  ←  seed_data.py (5 journeys, ~20 jobs, 3 schedules, 4 prompts)
  │
  └─► SSEManager (in-process, queue per subscriber)
```

No external dependencies. State lives in the pod's memory and is lost on
restart (feature, not bug — `seed_data.py` re-populates on boot).

## Tech stack

- **No bundler.** `index.html` loads React 18 + ReactDOM + `@babel/standalone`
  from `unpkg`. `app.js` is JSX transpiled in the browser. First load pays
  ~1.5 s Babel compile, then everything is cached.
- **No TypeScript.** Plain JavaScript with `React.createElement` / JSX.
- **No Tailwind / no bundler.** One hand-rolled dark-theme CSS file
  (`app.css`, ~350 LOC, no framework).
- **Hash routing.** `#/`, `#/journey/{id}`, `#/journey/{id}/jobs`,
  `#/schedules`, `#/prompts`. Works under any sub-path.
- **SSE via EventSource.** The logs drawer opens a connection to
  `GET /api/v1/journeys/{jid}/jobs/{jobId}/stream` and renders events
  into log lines as they arrive.

## File layout

```
src/nexus_ai_engine/server/
├── app.py                              # mounts routers + UI
├── routers/
│   ├── ui.py                           # / redirect, /ui, /ui/assets/*
│   ├── journeys.py                     # CRUD + stages
│   ├── jobs.py                         # run/cancel/retry/status/stream
│   ├── logs.py                         # get/search/errors
│   ├── reports.py                      # aggregate + per-job
│   ├── prompts.py                      # catalog + audit
│   ├── schedules.py                    # CRUD + run-now
│   └── _deps.py                        # FastAPI dependency for the engine
└── static/
    └── ui/
        ├── index.html                  # loads CDN React + /ui/assets/app.js
        ├── app.js                      # single-file React app (~900 LOC)
        ├── app.css                     # dark theme
        └── favicon.svg
```

## Adding a page

1. Add a `<XxxPage/>` component to `app.js`.
2. Add a route arm in `parseRoute()` and the `switch` block in `App`.
3. Add a nav link in `TopBar`.
4. If you need a new API call, extend the `api` object at the top of
   `app.js`.

Because there's no bundler, just save `app.js` and reload the browser.

## Adding an API route

1. Add the endpoint to the relevant router under
   `src/nexus_ai_engine/server/routers/`.
2. Add an `async def` on `InMemoryEngine` if it needs state.
3. Add a corresponding method to the `api` object in `app.js`.
4. Write an e2e test in `tests/e2e/test_journey_ui_api.py`.

## Limitations (by design)

- **In-memory only.** Restart the pod and you lose state; seed data
  repopulates. Persistence lands with the DynamoDB adapter in phase 10.
- **Simulated execution.** Jobs don't actually do work. The engine emits
  realistic-looking progress + log lines + a 5% random failure rate.
  Real executors land per stage as the library picks up nexus-backend's
  actual stage classes.
- **SSE is in-process.** If you scale beyond one pod and rely on SSE,
  route SSE traffic with sticky sessions or replace `EventSink` with a
  Redis-backed adapter.
- **No auth.** Anyone who can port-forward has full CRUD. Same risk
  profile as `kubectl exec`.
- **CDN dependency.** React, ReactDOM, and Babel Standalone load from
  `unpkg.com`. If you work from an air-gapped jumpbox, vendor them into
  `static/ui/vendor/` as a follow-up (~300 KB).

## Running the e2e tests

```bash
make test-e2e            # includes test_journey_ui_api.py + test_ui_static.py
make test-journeys       # includes test_runner_bound_to_app_runs_to_completion
```
