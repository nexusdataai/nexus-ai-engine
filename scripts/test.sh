#!/usr/bin/env bash
# Standalone test runner for nexus-ai-engine.
#
# Bootstraps a venv if none is active, installs the package with all extras,
# then runs exactly what CI runs. Zero external services required.
#
# Usage:
#   scripts/test.sh            # runs `make ci`
#   scripts/test.sh test-all   # runs any make target
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ ! -d .venv ]]; then
    echo "[test.sh] creating .venv ..."
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  pip install -e ".[dev,aws,test,server,harness]" >/dev/null
fi

TARGET="${1:-ci}"
shift || true
exec make "$TARGET" "$@"
