#!/usr/bin/env bash
#
# Container entrypoint: ensure DB is populated, then start uvicorn.
#
# We deliberately do NOT use `set -e` — we want uvicorn to start even if
# the ingestion check has an unexpected crash. A running-but-empty API
# is more debuggable than a restart-looping container.
#

echo "[start.sh] Checking database state..."
if ! uv run python -m promptarmor.ensure_db; then
    echo "[start.sh] WARNING: ensure_db exited non-zero. Starting server anyway."
fi

echo "[start.sh] Starting uvicorn on port ${PORT:-8000}..."
exec uv run uvicorn promptarmor.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
