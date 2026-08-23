#!/bin/bash
#
# port-forward-k3s-dev.sh — Forward shared nexus-local stack for ai-engine host dev.
#
# Usage:
#   ./scripts/port-forward-k3s-dev.sh
#   ./scripts/port-forward-k3s-dev.sh --kube-context local-cluster
#   ./scripts/stop-port-forward-k3s-dev.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOYER_ROOT="$(cd "${REPO_ROOT}/../nexus-deployer" && pwd)"
PID_FILE="${REPO_ROOT}/.k3s-port-forward-ai-engine.pids"

KUBE_CONTEXT="${KUBE_CONTEXT:-local-cluster}"
KUBECONFIG="${KUBECONFIG:-${DEPLOYER_ROOT}/aws-login/.kube/config}"
INFRA_NS="${INFRA_NS:-nexus-local}"

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

export KUBECONFIG

kctl() {
    kubectl --context "${KUBE_CONTEXT}" "$@"
}

if [[ -f "${PID_FILE}" ]]; then
    echo "Port-forwards may already be running (PID file: ${PID_FILE})"
    echo "Run: ${SCRIPT_DIR}/stop-port-forward-k3s-dev.sh"
    exit 1
fi

: > "${PID_FILE}"

_start_pf() {
    local name="$1"
    local ns="$2"
    local svc="$3"
    local local_port="$4"
    local remote_port="$5"
    kctl port-forward -n "${ns}" "svc/${svc}" "${local_port}:${remote_port}" >/dev/null 2>&1 &
    echo "$!" >> "${PID_FILE}"
    echo "  ${name}: 127.0.0.1:${local_port} -> ${ns}/${svc}:${remote_port}"
}

echo "Starting K3s port-forwards for nexus-ai-engine (context: ${KUBE_CONTEXT})"
echo ""

_start_pf "Scylla (DynamoDB)" "${INFRA_NS}" "scylla-svc" 8001 8000
_start_pf "MiniStack (Athena/Glue)" "${INFRA_NS}" "ministack-svc" 4566 4566
_start_pf "MinIO (S3)" "${INFRA_NS}" "minio-svc" 9000 9000

sleep 1
echo ""
echo "Port-forwards started. PID file: ${PID_FILE}"
echo "Stop with: ${SCRIPT_DIR}/stop-port-forward-k3s-dev.sh"
