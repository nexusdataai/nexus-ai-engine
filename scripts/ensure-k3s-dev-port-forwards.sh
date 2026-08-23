#!/bin/bash
#
# ensure-k3s-dev-port-forwards.sh — Start or restart port-forwards, then verify.
#
# Used by make dev-backend so the host backend always has K3s services available.
#
# Usage:
#   ./scripts/ensure-k3s-dev-port-forwards.sh [--kube-context local-cluster]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBE_CONTEXT="${KUBE_CONTEXT:-local-cluster}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --kube-context) KUBE_CONTEXT="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--kube-context NAME]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

export KUBE_CONTEXT

if "${SCRIPT_DIR}/verify-k3s-dev-services.sh" --quiet 2>/dev/null; then
    echo "K3s dev port-forwards OK"
    "${SCRIPT_DIR}/verify-k3s-dev-services.sh"
    exit 0
fi

echo "K3s dev services not reachable — (re)starting port-forwards..."
"${SCRIPT_DIR}/stop-port-forward-k3s-dev.sh" 2>/dev/null || true
pkill -f "port-forward.*nexus-local/scylla-svc" 2>/dev/null || true
pkill -f "port-forward.*nexus-local/ministack-svc" 2>/dev/null || true
pkill -f "port-forward.*nexus-local/minio-svc" 2>/dev/null || true
sleep 1

"${SCRIPT_DIR}/port-forward-k3s-dev.sh" --kube-context "${KUBE_CONTEXT}"
sleep 2

for i in 1 2 3 4 5 6 7 8 9 10; do
    if "${SCRIPT_DIR}/verify-k3s-dev-services.sh" --quiet 2>/dev/null; then
        "${SCRIPT_DIR}/verify-k3s-dev-services.sh"
        exit 0
    fi
    sleep 2
done

"${SCRIPT_DIR}/verify-k3s-dev-services.sh"
