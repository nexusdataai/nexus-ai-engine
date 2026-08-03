# Nexus AI Engine — Journey Studio (React SPA)

Production operator UI for v0.3.0. Replaces the embedded dev UI at `/ui` for fleet deployments.

## Stack

- Vite + React 18 + TypeScript
- Tailwind CSS (nexus-sre token palette)
- TanStack Query
- React Router

See `docs/spec/070-ui-specification.md`.

## Development

```bash
npm ci
# Terminal 1 — API
cd .. && make serve
# Terminal 2 — SPA (proxies /api → :8000)
npm run dev
```

Open http://localhost:5173

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server |
| `npm run build` | Production bundle → `dist/` |
| `npm run lint` | ESLint |
| `npm run test` | Vitest |

## Deployment

Built as `nexus-ai-engine-ui` nginx image via kube-operator (`ai-engine-ui` target).
