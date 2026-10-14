#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m uvicorn copilot.api:app --app-dir backend --host 127.0.0.1 --port 8000
fi
exec python3 -m uvicorn copilot.api:app --app-dir backend --host 127.0.0.1 --port 8000
