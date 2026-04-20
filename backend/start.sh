#!/usr/bin/env bash
#
# Container entrypoint: ensure DB is populated, then start uvicorn.
#
# Hard guarantee: uvicorn MUST start regardless of what ensure_db does.
# Prior symptom was Railway 502s caused by ensure_db hanging (network
# stall during dataset download) — bash's `if !` only catches non-zero
# exits, not hangs. We wrap with `timeout` so no matter what, the server
# starts within ~3 minutes and serves whatever data is present
# (taxonomy handles empty DB gracefully).
#
# `set -e` is deliberately OFF — a running-with-empty-DB API is more
# debuggable than a restart-looping container.
#

ENSURE_DB_TIMEOUT_SECONDS="${ENSURE_DB_TIMEOUT_SECONDS:-180}"

echo "[start.sh] Checking database state (timeout ${ENSURE_DB_TIMEOUT_SECONDS}s)..."
timeout --kill-after=10 "${ENSURE_DB_TIMEOUT_SECONDS}" \
    uv run python -m promptarmor.ensure_db
ensure_db_status=$?

case "$ensure_db_status" in
    0)
        echo "[start.sh] ensure_db OK."
        ;;
    124)
        echo "[start.sh] WARNING: ensure_db timed out after ${ENSURE_DB_TIMEOUT_SECONDS}s. Starting server anyway."
        ;;
    *)
        echo "[start.sh] WARNING: ensure_db exited ${ensure_db_status}. Starting server anyway."
        ;;
esac

echo "[start.sh] Starting uvicorn on port ${PORT:-8000}..."
exec uv run uvicorn promptarmor.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
