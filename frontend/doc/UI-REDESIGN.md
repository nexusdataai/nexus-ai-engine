# Nexus AI Engine UI redesign

Branch: `ui-redesign`. The engine console now uses the same design system as
the Nexus AI ontology product and the website: graphite surfaces, one blue
accent (`#3d73ff`), Geist type, the Nexus AI "N" mark, and the UIcons icon
family.

Scope: **UI only.** Nothing under `backend/`, `src/services/`, `src/hooks/`,
`src/types/` or `src/lib/` was changed. API calls, query keys, mutations,
confirm texts and every `data-testid` are the same as before, so the existing
unit tests and the Playwright UAT keep working.

## What changed

| Area | What it is now |
|---|---|
| Shell | Grouped sidebar (Overview, Runtime, Automation, AI Ops), collapsible to icons, drawer on phones. Top bar with breadcrumbs, environment, version, theme switch, sign-in. |
| Dashboard | A live pipeline (Journeys → Queue → Running on workers → Results) whose connectors animate while work is moving, hourly throughput chart, worker health, recent runs. |
| Executions | Search, status filters with counts, date range, selection bar for bulk delete, table in pages of 100. |
| Queue | One metric strip, a waiting lane feeding the running slots, jobs table with wait time. |
| Workers | Replica rail (ready / starting / headroom, autoscaling range), registry table, scaling controls in one side panel. |
| Journeys | Search, filters (active now, with failures, idle), cards with a success bar or a table view, selection bar for bulk run. |
| Journey / Stage job | Vertical workflow pipeline, log console that follows the tail, job history / schedules / archive as tabs. |
| DSL studio | Three panes in one frame: stages, YAML editor, tool picker. Validate / Run / Save in the header. |
| Schedules | Table with on/off switches, create/edit dialog, archive search in its own tab with a side sheet for logs. |
| Tools | Catalogue cards with domain and capabilities. |
| Operations | Same sections and labels, rebuilt on the shared kit. |
| Settings | Side menu (Workers, Queue, Scheduler, About), one form per section. |

Small behaviour changes, all on the UI side:

- A journey whose backend status is the legacy `pending` and has nothing in
  flight is shown as **Idle**.
- Deleting a schedule now asks for confirmation first.
- The journey page opens on the first step, so the log console is not blank.
- Run rows are keyed by journey + job id (job ids repeat across journeys,
  which produced duplicate-key warnings before).

## Where things live

```
src/styles.css                 base styles, fonts, form/table utility classes
src/styles/tokens.css          colour, type, radius, shadow, motion tokens (light + dark)
src/styles/utils.css           keyframes, reduced-motion rule
src/styles/charts.css          Recharts defaults
src/components/ds/kit.tsx      PageHeader, Panel, MetricStrip, StatusPill, Chips, Segmented,
                               LineTabs, KeyValues, Meter, CodeBlock, DetailSheet, Modal,
                               Field, InlineError, Notice, TableShell, Skeleton, EmptyState
src/components/ds/charts.tsx   one palette, tooltip, axis and motion for every chart
src/components/ds/Icon.tsx     <Icon name="…" /> (icons.generated.ts is the compiled set)
src/components/ds/Logo.tsx     brand mark and wordmark
src/config/navigation.ts       sidebar groups and breadcrumbs (add a screen here)
tailwind.config.js             Tailwind wired to the tokens
```

## Rules for new screens

1. Never hard-code a colour. Use the token classes: `bg-card`, `bg-surface-2`,
   `border-border`, `text-foreground`, `text-muted-foreground`,
   `text-primary dark:text-brand-hi`, `text-success`, `text-warning`,
   `text-destructive`.
2. Status is always `<StatusPill status={…} />` (a dot and a word). Green,
   amber and red are only for status.
3. Headline numbers go in one `<MetricStrip>`; do not build a grid of
   separate stat cards with icons.
4. One `<Panel>` per object; never a card inside a card. Tables use
   `<table className="tbl">` inside `<Panel flush>` or `<TableShell>`;
   right-align numbers with `className="r num"`.
5. Inputs and selects use `className="field"`, checkboxes `className="check"`.
6. Loading is `Skeleton` / `SkeletonRows`, empty is `EmptyState`, failure is
   `InlineError`, the result of an action is `Notice`.
7. Charts use the helpers in `ds/charts.tsx`: blue first, light blue second.
8. Page titles are `<PageHeader>` (it renders an `<h2>`; the tests look for it).

## Run it locally

```
cd frontend
npm ci
cp .env.local.k3s.example .env.local   # optional
npm run dev
```

`vite.config.ts` reads `VITE_PROXY_TARGET` from `.env.local`. Leave it unset
to proxy the API to a backend on `http://127.0.0.1:8000`, or point it at
another engine to see real data.

Checks: `npx tsc -b`, `npm test`, `npm run build`.

## Open items

- `frontend/src/lib/` (`utils.ts`, `stageJourney.ts`) is not in the GitHub
  repository: the root `.gitignore` has a Python `lib/` rule that also hides
  this folder, so a fresh clone does not build. Suggested fix: add
  `!frontend/src/lib/` to `.gitignore` and commit the folder.
- `frontend/node_modules` is partly committed. It should be removed from git
  (`git rm -r --cached frontend/node_modules`) and ignored.
- Icons are Freepik UIcons (Flaticon licence): covered by an active
  Freepik / Magnific subscription, otherwise a credit to Flaticon is needed.
