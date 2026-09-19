#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/runpod/.venv/bin/python}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5173}"

export MODEL_PROFILE="${MODEL_PROFILE:-kanana}"
export ADAPTER_NAME="${ADAPTER_NAME:-iri-kanana3b-tuned}"
export BEHAVIOR_PROFILE="${BEHAVIOR_PROFILE:-kanana_v5}"

cd "$ROOT"

"$PYTHON_BIN" -m uvicorn api.app.app:app --host "$API_HOST" --port "$API_PORT" &
api_pid=$!
"$ROOT/web/node_modules/.bin/vite" "$ROOT/web" --host "$WEB_HOST" --port "$WEB_PORT" --strictPort &
web_pid=$!

cleanup() {
  kill "$api_pid" "$web_pid" 2>/dev/null || true
  wait "$api_pid" "$web_pid" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do
  sleep 1
done

status=0
if ! kill -0 "$api_pid" 2>/dev/null; then
  wait "$api_pid" || status=$?
else
  wait "$web_pid" || status=$?
fi

exit "$status"
