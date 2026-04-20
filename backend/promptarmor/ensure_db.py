"""Startup check: ensure the database is populated.

Runs before uvicorn starts. If the attack_prompts table is missing, empty,
or only partially populated (e.g. an earlier ingestion was interrupted after
inserting prompts but before classifying techniques), triggers the ingestion
pipeline with safe defaults.

Failure mode: logs the exception and exits 0. The taxonomy endpoint handles
an empty DB gracefully (returns zeros, not 500), so serving a visibly-empty
app is more debuggable than crashing the container with no logs.

Boot-time ingestion can be disabled in production by setting
`DISABLE_BOOT_INGEST=true` — in that case the server starts with whatever
data the mounted volume provides and logs a warning if that data is missing
or incomplete.
"""

import argparse
import asyncio
import logging
import sqlite3

from promptarmor.config import settings

logger = logging.getLogger(__name__)

def _has_data() -> bool:
    """Return True if the DB looks healthy and ready to serve.

    Returns False if:
    - The DB file doesn't exist yet (fresh volume)
    - The required tables don't exist yet (schema uninitialized)
    - attack_prompts is empty
    - prompt_techniques is empty (ingestion crashed after inserting prompts
      but before classifying techniques — the taxonomy page would be broken)

    Intentionally permissive on row counts: on a memory-constrained prod
    container, re-triggering ingestion can OOM-kill the whole process. We'd
    rather serve a slightly-small DB than restart-loop the container.
    """
    if not settings.db_path.exists():
        return False
    try:
        with sqlite3.connect(str(settings.db_path)) as conn:
            attack_count = conn.execute(
                "SELECT COUNT(*) FROM attack_prompts"
            ).fetchone()[0]
            if attack_count == 0:
                return False
            technique_count = conn.execute(
                "SELECT COUNT(*) FROM prompt_techniques"
            ).fetchone()[0]
            return bool(technique_count > 0)
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

    if settings.disable_boot_ingest:
        logger.warning(
            "Database is empty or incomplete AND DISABLE_BOOT_INGEST is set — "
            "server will start with a degraded dataset. "
            "Mount a pre-populated volume or unset the flag to re-enable boot ingest."
        )
        return

    logger.warning("Database is empty or incomplete — running ingestion pipeline (~3 min)...")
    try:
        asyncio.run(_run_ingestion())
        logger.info("Ingestion complete.")
    except Exception:
        logger.exception("Ingestion failed — server will start with empty DB.")


if __name__ == "__main__":
    main()
