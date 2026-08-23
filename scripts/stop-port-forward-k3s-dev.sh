#!/bin/bash
#
# stop-port-forward-k3s-dev.sh — Stop port-forwards started by port-forward-k3s-dev.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${REPO_ROOT}/.k3s-port-forward-ai-engine.pids"

if [[ ! -f "${PID_FILE}" ]]; then
    echo "No port-forward PID file at ${PID_FILE}"
    exit 0
fi

while read -r pid; do
    [[ -z "${pid}" ]] && continue
    if kill "${pid}" 2>/dev/null; then
        echo "Stopped PID ${pid}"
    fi
done < "${PID_FILE}"

rm -f "${PID_FILE}"
echo "Port-forwards stopped"
