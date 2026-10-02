#!/bin/bash
#
# port-forward-ui-k3s.sh — Forward Journey Studio UI (ai-engine-local frontend) to localhost:8080.
#
# Run this in a Cursor integrated terminal so the Ports panel can tunnel 8080 to your laptop.
#
# Usage:
#   ./scripts/port-forward-ui-k3s.sh
#   ./scripts/stop-port-forward-ui-k3s.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOYER_ROOT="$(cd "${REPO_ROOT}/../nexus-deployer" && pwd)"
PID_FILE="${REPO_ROOT}/.k3s-port-forward-ui.pids"

KUBE_CONTEXT="${KUBE_CONTEXT:-local-cluster}"
KUBECONFIG="${KUBECONFIG:-${DEPLOYER_ROOT}/aws-login/.kube/config}"
NAMESPACE="${AI_ENGINE_NAMESPACE:-ai-engine-local}"
SVC="${AI_ENGINE_FRONTEND_SVC:-ai-engine-local-frontend-svc}"
LOCAL_PORT="${AI_ENGINE_UI_PORT:-8080}"

export KUBECONFIG

kctl() {
    kubectl --context "${KUBE_CONTEXT}" "$@"
}

if [[ -f "${PID_FILE}" ]]; then
    while read -r pid; do
        [[ -z "${pid}" ]] && continue
        if kill -0 "${pid}" 2>/dev/null; then
            echo "UI port-forward already running (PID ${pid})."
            echo "Stop with: ${SCRIPT_DIR}/stop-port-forward-ui-k3s.sh"
            exit 0
        fi
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
fi

if ! kctl -n "${NAMESPACE}" get svc "${SVC}" >/dev/null 2>&1; then
    echo "Service ${NAMESPACE}/${SVC} not found. Is ai-engine-local deployed?" >&2
    exit 1
fi

: > "${PID_FILE}"
kctl -n "${NAMESPACE}" port-forward "svc/${SVC}" "${LOCAL_PORT}:8080" &
echo "$!" >> "${PID_FILE}"

sleep 1
if ! kill -0 "$(tail -1 "${PID_FILE}")" 2>/dev/null; then
    echo "Port-forward failed to start. Check ${NAMESPACE}/${SVC} and kubeconfig." >&2
    rm -f "${PID_FILE}"
    exit 1
fi

echo "Journey Studio UI: http://127.0.0.1:${LOCAL_PORT}"
echo "  Remote: ${NAMESPACE}/${SVC} -> localhost:${LOCAL_PORT}"
echo "  PID file: ${PID_FILE}"
echo ""
echo "In Cursor: open the Ports tab, forward port ${LOCAL_PORT}, then open in browser."
echo "Stop with: ${SCRIPT_DIR}/stop-port-forward-ui-k3s.sh"

wait
