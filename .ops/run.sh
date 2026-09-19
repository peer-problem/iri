#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export BEHAVIOR_PROFILE="${BEHAVIOR_PROFILE:-kanana_v5}"
cd "$ROOT"

runpod/.venv/bin/uvicorn api.app.app:app --host 127.0.0.1 --port 8000 &
api_pid=$!
npm run dev --prefix web &
web_pid=$!

cleanup() {
  trap - EXIT INT TERM
  kill "$api_pid" "$web_pid" 2>/dev/null || true
  wait "$api_pid" "$web_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM
wait "$api_pid" "$web_pid"
