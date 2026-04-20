#!/usr/bin/env bash
#
# Container entrypoint: ensure DB is populated, then start uvicorn.
#
# Exits non-zero if uvicorn fails to start (via `exec`), but tolerates
# ingestion failures — ensure_db.py logs and continues so the server
# can still boot and serve the (empty) API.
#
set -euo pipefail

echo "[start.sh] Checking database state..."
uv run python -m promptarmor.ensure_db

echo "[start.sh] Starting uvicorn on port ${PORT:-8000}..."
exec uv run uvicorn promptarmor.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
