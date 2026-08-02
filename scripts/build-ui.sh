#!/usr/bin/env bash
# Pre-compile embedded UI JSX to app.bundle.js (avoids in-browser Babel).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! command -v npx >/dev/null; then
  echo "npx required" >&2
  exit 1
fi
npm install --no-save @babel/core @babel/cli @babel/preset-env @babel/preset-react >/dev/null 2>&1 || true
npx babel backend/src/nexus_ai_engine/server/static/ui/app.js \
  --out-file backend/src/nexus_ai_engine/server/static/ui/app.bundle.js
echo "Wrote app.bundle.js"
