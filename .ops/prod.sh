#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT/runpod/.venv/bin/python"

cd "$ROOT"
"$PYTHON_BIN" api/deploy/deploy.py vps
exec "$PYTHON_BIN" api/deploy/deploy.py vercel
