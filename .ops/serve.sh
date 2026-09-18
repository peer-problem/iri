#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
ADAPTER_RUN="${ADAPTER_RUN:-/workspace/iri-adapter-run}"

cd "$ROOT"
exec "$PYTHON_BIN" -m runpod.operations.serve_model \
  --adapter-run "$ADAPTER_RUN" \
  --prefix-caching on \
  --batch-invariant
