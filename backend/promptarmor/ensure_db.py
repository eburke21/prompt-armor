"""Startup check: ensure the database is populated.

Runs before uvicorn starts. If the attack_prompts table is empty (or the DB
file doesn't exist), triggers the ingestion pipeline with safe defaults.
Otherwise no-op and exits quickly so the server can start.

Failure mode: logs the exception and exits 0. The taxonomy endpoint handles
an empty DB gracefully (returns zeros, not 500), so serving a visibly-empty
app is more debuggable than crashing the container with no logs.
"""

import argparse
import asyncio
import logging
import sqlite3

from promptarmor.config import settings

logger = logging.getLogger(__name__)


def _has_data() -> bool:
    """Return True if attack_prompts has at least one row.

    Returns False if:
    - The DB file doesn't exist yet (fresh volume)
    - The attack_prompts table doesn't exist yet (schema uninitialized)
    - The table exists but is empty (interrupted previous ingestion)
    """
    if not settings.db_path.exists():
        return False
    try:
        with sqlite3.connect(str(settings.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM attack_prompts").fetchone()[0]
            return bool(count > 0)
    except sqlite3.OperationalError:
        return False


async def _run_ingestion() -> None:
    """Invoke the ingestion pipeline with production-safe defaults."""
    from promptarmor.ingestion.__main__ import main as ingest_main

    args = argparse.Namespace(
        datasets=None,   # all datasets
        skip_llm=True,   # heuristic-only: avoids API cost on fresh boots
        sample=None,     # full ingest
        verbose=False,
    )
    await ingest_main(args)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [ensure_db]: %(message)s",
    )

    if _has_data():
        logger.info("Database already populated — skipping ingestion.")
        return

    logger.warning("Database is empty — running ingestion pipeline (~3 min)...")
    try:
        asyncio.run(_run_ingestion())
        logger.info("Ingestion complete.")
    except Exception:
        logger.exception("Ingestion failed — server will start with empty DB.")


if __name__ == "__main__":
    main()
