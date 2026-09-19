#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
ADAPTER_RUN="${ADAPTER_RUN:-/workspace/iri-adapter-run}"
PREFIX_CACHING="${PREFIX_CACHING:-on}"
BATCH_INVARIANT="${BATCH_INVARIANT:-1}"

export MODEL_PROFILE="${MODEL_PROFILE:-kanana}"
export MODEL_REVISION="${MODEL_REVISION:-6a5d7889964c4c590299d16e309eabab1f73f8a9}"
export ADAPTER_NAME="${ADAPTER_NAME:-iri-kanana3b-v5-0ecacdb7d7f7}"
export ADAPTER_REVISION="${ADAPTER_REVISION:-0880ce0372cedf22aec91b190f8a7b9499ccc176}"
export ADAPTER_SHA256="${ADAPTER_SHA256:-0ecacdb7d7f743652a24ff7b7e7c59d0e2ae238e63476e64b2d6d95e8fbe2e02}"
export BEHAVIOR_PROFILE="${BEHAVIOR_PROFILE:-kanana_v5}"
export MODEL_SERVE_PORT="${MODEL_SERVE_PORT:-8002}"

cd "$ROOT"

serve_args=(
  -m runpod.operations.serve_model
  --adapter-run "$ADAPTER_RUN"
  --prefix-caching "$PREFIX_CACHING"
)

case "$BATCH_INVARIANT" in
  1|true|on)
    serve_args+=(--batch-invariant)
    ;;
  0|false|off)
    ;;
  *)
    echo "BATCH_INVARIANT must be one of: 1, true, on, 0, false, off" >&2
    exit 2
    ;;
esac

exec "$PYTHON_BIN" "${serve_args[@]}"
