#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/runpod/.venv/bin/python}"
PRODUCTION_ORIGIN="${PRODUCTION_ORIGIN:-https://iri.today}"

cd "$ROOT"
"$PYTHON_BIN" api/deploy/deploy.py domains
"$PYTHON_BIN" api/deploy/deploy.py vps --origin "$PRODUCTION_ORIGIN"
exec "$PYTHON_BIN" api/deploy/deploy.py vercel
