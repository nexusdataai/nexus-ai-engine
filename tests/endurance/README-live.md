# Live endurance (bulk-run 55 journeys)

In-process endurance tests under `tests/endurance/*.py` stay offline. **Live** tests hit a real deployment in queue mode.

## Run (30 minutes default)

```bash
cd nexus-ai-engine
source .venv/bin/activate

export ENDURANCE_BASE_URL=https://ai-engine.yourbrain.tech
# optional: shorter smoke before a full soak
# export ENDURANCE_DURATION_SECONDS=300

pytest tests/endurance/live -q -m live
# or
make test-endurance-live
```

## Without pytest

```bash
export ENDURANCE_BASE_URL=https://ai-engine.yourbrain.tech
python -m tests.endurance.live.soak_runner
```

## What it checks

Each cycle until the duration elapses:

1. `GET /api/v1/journeys/?limit=1000` — collect all `journeyId` values (expects ≥55).
2. `POST /api/v1/journeys/bulk-run` — enqueue every journey; fails if `failed > 0` or `queued != count`.
3. Poll `GET /api/v1/queue/summary` and `GET /api/v1/queue/jobs` until lag/active/queued are zero.
4. Record **502/503**, transport errors, slow responses, and drain timeouts.

JSON report: `tests/reports/endurance/bulk_run_55_soak.json` (override with `ENDURANCE_REPORT_PATH`).

## Useful toggles

| Variable | Default | Meaning |
|----------|---------|---------|
| `ENDURANCE_DURATION_SECONDS` | `1800` | Total soak wall time |
| `ENDURANCE_DRAIN_TIMEOUT_SECONDS` | `1200` | Per-cycle queue idle timeout |
| `ENDURANCE_SUMMARY_MAX_SECONDS` | `5` | Max acceptable `/queue/summary` latency |
| `ENDURANCE_JOBS_MAX_SECONDS` | `15` | Max acceptable `/queue/jobs` latency |
| `ENDURANCE_POLL_INTERVAL_SECONDS` | `10` | Poll interval while draining |
| `ENDURANCE_QUEUE_PURGE_BETWEEN_CYCLES` | `false` | `POST /queue/purge` before each cycle after the first |
