#!/bin/bash

# Seed sample journeys against a running nexus-ai-engine instance.
#
# Reads canonical journey definitions from the library itself by invoking
# `nexus-ai-engine print-demo-journeys` (which dumps the same DEMO_JOURNEYS
# constant the runtime registers stage classes from). One source of truth
# means the seeded journeys' stage_ids and step_ids are always aligned
# with the registered DemoStage classes, so clicking "Start Processing"
# in the UI actually executes the steps end-to-end through the
# production engine.
#
# Where to run from:
#   * Inside the pod:                BASE_URL=http://127.0.0.1:8000   ./scripts/seed-sample-journeys.sh
#   * EC2 host w/ port-forward:      BASE_URL=http://127.0.0.1:18000  ./scripts/seed-sample-journeys.sh
#   * Anywhere reachable:            BASE_URL=https://your.ingress    ./scripts/seed-sample-journeys.sh
#
# Default BASE_URL is http://127.0.0.1:8000 (in-pod). Pass --force to
# skip the "is the journeys list empty" safety check.
#
# The script needs the `nexus-ai-engine` console script on PATH so it
# can fetch the canonical definitions. Inside the pod this is always
# present (the image installs it as the entrypoint); on the EC2 host
# activate the venv first (`source .venv/bin/activate`).
#
# Two-pass behaviour:
#   1. POST /api/v1/journeys/  — create the journey record (legacy
#      router accepts a `stages` payload field but silently drops it).
#   2. POST /api/v1/journeys/{id}/stages — add each stage individually
#      via the dedicated endpoint that actually persists.
# Step lists are recovered at render time by the v2 UI from the
# registered stage class metadata via /api/v1/stages/registered, so
# we don't push steps here.
#
# Exit codes:
#   0  all journeys created (or already existed)
#   2  bad CLI args
#   3  curl / python3 / nexus-ai-engine missing or API unreachable
#   4  one or more create / add_stage calls failed (script keeps going)

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
FORCE="false"
APPEND="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)    FORCE="true"; shift ;;
        --append)   APPEND="true"; shift ;;
        --base)     BASE_URL="$2"; shift 2 ;;
        --help|-h)
            sed -n '3,40p' "$0"
            exit 0 ;;
        *)
            echo "Unknown arg: $1" >&2
            echo "Usage: $0 [--base http://host:port] [--force] [--append]" >&2
            exit 2 ;;
    esac
done

command -v curl    >/dev/null || { echo "curl not on PATH"    >&2; exit 3; }
command -v python3 >/dev/null || { echo "python3 not on PATH" >&2; exit 3; }
command -v nexus-ai-engine >/dev/null || {
    echo "nexus-ai-engine console script not on PATH" >&2
    echo "  Inside the pod:  it's always present (image entrypoint)." >&2
    echo "  EC2 host:        activate the venv first: source .venv/bin/activate" >&2
    exit 3
}

echo "Target: ${BASE_URL}"

# ── Connectivity probe ──────────────────────────────────────────────────
if ! version_body=$(curl -fsS -m 5 "${BASE_URL}/version" 2>&1); then
    echo "ERROR: cannot reach ${BASE_URL}/version" >&2
    echo "       ${version_body}" >&2
    echo "Hints:" >&2
    echo "  * Inside pod:   leave BASE_URL unset (default :8000)." >&2
    echo "  * EC2 host:     start port-forward then BASE_URL=http://127.0.0.1:18000 $0" >&2
    exit 3
fi
echo "  version: ${version_body}"

# ── Optional safety: bail if journeys already exist ─────────────────────
existing_count=$(curl -fsS -m 5 "${BASE_URL}/api/v1/journeys/" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("total", len(d) if isinstance(d, list) else 0))')
if [[ "$existing_count" != "0" && "$FORCE" != "true" && "$APPEND" != "true" ]]; then
    echo
    echo "Journeys already exist (total=${existing_count}). Pass --force to seed anyway or --append for missing only."
    echo "View existing: ${BASE_URL}/ui#/"
    exit 0
fi

existing_names=""
if [[ "$APPEND" == "true" ]]; then
    existing_names=$(curl -fsS -m 5 "${BASE_URL}/api/v1/journeys/" | python3 -c '
import json, sys
d = json.load(sys.stdin)
items = d.get("data") or d.get("journeys") or (d if isinstance(d, list) else [])
for row in items:
    if isinstance(row, dict) and row.get("name"):
        print(row["name"])
')
fi

# ── Fetch canonical definitions from the library ────────────────────────
demo_journeys_json=$(nexus-ai-engine print-demo-journeys 2>/dev/null) || {
    echo "ERROR: 'nexus-ai-engine print-demo-journeys' failed" >&2
    exit 3
}
journey_count=$(printf '%s' "$demo_journeys_json" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')

# ── Iterate: create each journey, then add its stages ───────────────────
: > /tmp/_seed_ids
FAILED="false"

echo
echo "Creating ${journey_count} sample journeys (canonical definitions from nexus-ai-engine)..."

while IFS=$'\t' read -r jname jpayload jstages_json; do
    [[ -z "$jname" ]] && continue
    if [[ "$APPEND" == "true" ]] && printf '%s\n' "$existing_names" | grep -Fxq "$jname"; then
        printf "  · %-32s  skipped (exists)\n" "$jname"
        continue
    fi

    # Pass 1: create the journey
    resp=$(curl -sS -o /tmp/_seed_resp -w '%{http_code}' \
        -X POST "${BASE_URL}/api/v1/journeys/" \
        -H 'content-type: application/json' \
        -d "$jpayload" 2>&1) || true
    body=$(cat /tmp/_seed_resp 2>/dev/null || echo '{}')
    if [[ ! "$resp" =~ ^2 ]]; then
        printf "  ✗ %-32s  http=%s body=%s\n" "$jname" "$resp" "${body:0:200}"
        FAILED="true"
        continue
    fi
    jid=$(printf '%s' "$body" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("journey_id") or (d.get("data") or {}).get("journey_id") or (d.get("data") or {}).get("journeyId") or "?")
except Exception:
    print("?")
')
    printf "  ✓ %-32s  id=%s\n" "$jname" "$jid"
    echo "$jid" >> /tmp/_seed_ids
    [[ "$jid" == "?" ]] && continue

    # Pass 2: POST add_stage for each stage in this journey. The legacy
    # `POST /api/v1/journeys/` accepts a `stages` payload field but silently
    # drops it; the dedicated `POST /{id}/stages` endpoint persists.
    printf '%s' "$jstages_json" | python3 -c '
import json, sys, urllib.parse
for i, s in enumerate(json.load(sys.stdin), start=1):
    print(urllib.parse.urlencode({
        "stage_id":    s["stage_id"],
        "name":        s["name"],
        "description": s.get("description", ""),
        "order":       s.get("order", i),
    }))
' | while IFS= read -r qs; do
        [[ -z "$qs" ]] && continue
        sresp=$(curl -sS -o /tmp/_seed_resp -w '%{http_code}' \
            -X POST "${BASE_URL}/api/v1/journeys/${jid}/stages?${qs}" \
            -H 'content-type: application/json' \
            -d '{}' 2>&1) || true
        sbody=$(cat /tmp/_seed_resp 2>/dev/null || echo '{}')
        if [[ ! "$sresp" =~ ^2 ]]; then
            printf "      ✗ add_stage  qs=%s  http=%s body=%s\n" \
                "${qs:0:60}" "$sresp" "${sbody:0:120}"
            FAILED="true"
        fi
    done
done < <(printf '%s' "$demo_journeys_json" | python3 -c '
import json, sys

# JourneyCreateRequest payload + a third TAB-separated field carrying
# the canonical stages array as raw JSON for the second-pass loop.
# String concatenation (not f-string) avoids quote-escape collisions
# inside the surrounding bash single-quoted heredoc.
for j in json.load(sys.stdin):
    payload = {
        "name":             j["name"],
        "description":      j.get("description"),
        "odaComponentType": j["odaComponentType"],
        "priority":         j.get("priority", "medium"),
        "stages":           j["stages"],
    }
    sys.stdout.write(
        j["name"] + "\t" + json.dumps(payload) + "\t" + json.dumps(j["stages"]) + "\n"
    )
')

echo
echo "Done."
if [[ "$FAILED" == "true" ]]; then
    echo "One or more creates / add_stage calls failed (see ✗ rows above)."
    exit 4
fi

# ── Pretty links ────────────────────────────────────────────────────────
ids=$(cat /tmp/_seed_ids 2>/dev/null || true)
if [[ -n "$ids" ]]; then
    echo
    echo "Open the v2 UI for any of these:"
    while read -r jid; do
        [[ -z "$jid" || "$jid" == "?" ]] && continue
        echo "  ${BASE_URL}/ui#/journey/${jid}/v2"
    done <<< "$ids"
    echo
    echo "Or land on the journeys list:  ${BASE_URL}/ui#/"
fi

rm -f /tmp/_seed_resp /tmp/_seed_ids

echo
echo "Each journey now has its stages persisted. Steps are surfaced at"
echo "render time by the v2 UI from the registered stage class metadata"
echo "(/api/v1/stages/registered), so the stepper shows real step lists"
echo "and 'Start Processing' executes them end-to-end."
echo
echo "Disable demo stage registration with REGISTER_DEMO_STAGES=false in"
echo "the deployment ConfigMap once a host registers real stages."
