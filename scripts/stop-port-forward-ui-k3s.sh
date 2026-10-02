#!/bin/bash
#
# stop-port-forward-ui-k3s.sh — Stop UI port-forward from port-forward-ui-k3s.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${REPO_ROOT}/.k3s-port-forward-ui.pids"

if [[ ! -f "${PID_FILE}" ]]; then
    pkill -f "port-forward.*ai-engine-local-frontend-svc" 2>/dev/null || true
    echo "No UI port-forward PID file; cleaned up any matching kubectl processes."
    exit 0
fi

while read -r pid; do
    [[ -z "${pid}" ]] && continue
    if kill "${pid}" 2>/dev/null; then
        echo "Stopped PID ${pid}"
    fi
done < "${PID_FILE}"

rm -f "${PID_FILE}"
echo "UI port-forward stopped"
