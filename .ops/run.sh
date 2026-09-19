#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/runpod/.venv/bin/python}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5173}"

export MODEL_PROFILE="${MODEL_PROFILE:-kanana}"
export ADAPTER_NAME="${ADAPTER_NAME:-iri-kanana3b-v5-0ecacdb7d7f7}"
export ADAPTER_REVISION="${ADAPTER_REVISION:-0880ce0372cedf22aec91b190f8a7b9499ccc176}"
export ADAPTER_SHA256="${ADAPTER_SHA256:-0ecacdb7d7f743652a24ff7b7e7c59d0e2ae238e63476e64b2d6d95e8fbe2e02}"
export BEHAVIOR_PROFILE="${BEHAVIOR_PROFILE:-kanana_v5}"
export ALLOW_DEV_ACCESS_CODE="${ALLOW_DEV_ACCESS_CODE:-true}"

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
