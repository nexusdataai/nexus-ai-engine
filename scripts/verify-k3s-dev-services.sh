#!/bin/bash
#
# verify-k3s-dev-services.sh — Health-check K3s port-forwarded dev endpoints.
#
# Usage:
#   ./scripts/verify-k3s-dev-services.sh
#   ./scripts/verify-k3s-dev-services.sh --quiet
#

set -euo pipefail

QUIET=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quiet|-q) QUIET=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--quiet]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

log() { [[ "${QUIET}" == true ]] || echo "$@"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

_check_tcp() {
    local name="$1" host="$2" port="$3"
    if (echo >/dev/tcp/"${host}"/"${port}") 2>/dev/null; then
        log "  OK  ${name} (${host}:${port})"
        return 0
    fi
    log "  FAIL ${name} (${host}:${port}) — not reachable"
    return 1
}

_check_ministack() {
    local body
    body=$(curl -sf --max-time 5 "http://127.0.0.1:4566/_localstack/health" 2>/dev/null) || {
        log "  FAIL MiniStack (127.0.0.1:4566) — health check failed"
        return 1
    }
    if echo "${body}" | grep -q '"dynamodb"'; then
        log "  OK  MiniStack Athena/Glue (127.0.0.1:4566)"
        return 0
    fi
    log "  FAIL MiniStack (127.0.0.1:4566) — unexpected health response"
    return 1
}

_check_scylla_ddb() {
    if ! _check_tcp "Scylla DynamoDB" "127.0.0.1" "8001"; then
        return 1
    fi
    local body
    body=$(curl -sf --max-time 5 -X POST "http://127.0.0.1:8001/" \
        -H "Content-Type: application/x-amz-json-1.0" \
        -H "X-Amz-Target: DynamoDB_20120810.ListTables" \
        -d '{}' 2>/dev/null) || {
        log "  FAIL Scylla DynamoDB API — port open but Alternator not responding"
        return 1
    }
    if echo "${body}" | grep -q 'TableNames'; then
        log "  OK  Scylla DynamoDB API (ListTables)"
        return 0
    fi
    log "  FAIL Scylla DynamoDB API — unexpected response: ${body:0:120}"
    return 1
}

errors=0
log "Verifying K3s dev port-forwards (nexus-ai-engine)..."

_check_scylla_ddb || errors=$((errors + 1))
_check_ministack || errors=$((errors + 1))
_check_tcp "MinIO S3" "127.0.0.1" "9000" || errors=$((errors + 1))

if [[ "${errors}" -gt 0 ]]; then
    fail "${errors} required service(s) unreachable. Run: make port-forward-k3s"
fi

log "All required K3s dev services are reachable."
exit 0
