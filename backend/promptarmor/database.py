import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite

from promptarmor.config import settings

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Core attack prompt storage
CREATE TABLE IF NOT EXISTS attack_prompts (
    id TEXT PRIMARY KEY,
    source_dataset TEXT NOT NULL,
    original_label TEXT NOT NULL,
    is_injection BOOLEAN NOT NULL,
    prompt_text TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    difficulty_estimate INTEGER,
    character_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: prompts can have multiple technique tags
CREATE TABLE IF NOT EXISTS prompt_techniques (
    prompt_id TEXT NOT NULL REFERENCES attack_prompts(id),
    technique TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    classified_by TEXT NOT NULL,
    PRIMARY KEY (prompt_id, technique)
);

-- System prompts from SPML dataset (and user-submitted)
CREATE TABLE IF NOT EXISTS system_prompts (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    name TEXT,
    prompt_text TEXT NOT NULL,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Evaluation runs
CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    defense_config JSON NOT NULL,
    attack_set_config JSON NOT NULL,
    status TEXT DEFAULT 'pending',
    total_prompts INTEGER NOT NULL,
    completed_prompts INTEGER DEFAULT 0,
    summary_stats JSON
);

-- Individual test results within an eval run
CREATE TABLE IF NOT EXISTS eval_results (
    id TEXT PRIMARY KEY,
    eval_run_id TEXT NOT NULL REFERENCES eval_runs(id),
    prompt_id TEXT NOT NULL REFERENCES attack_prompts(id),
    is_injection BOOLEAN NOT NULL,
    input_filter_blocked BOOLEAN DEFAULT FALSE,
    input_filter_type TEXT,
    input_filter_score REAL,
    llm_response TEXT,
    llm_latency_ms INTEGER,
    output_filter_blocked BOOLEAN DEFAULT FALSE,
    output_filter_type TEXT,
    output_filter_score REAL,
    injection_succeeded BOOLEAN,
    blocked_by TEXT,
    semantic_eval_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_prompts_injection ON attack_prompts(is_injection);
CREATE INDEX IF NOT EXISTS idx_prompts_source ON attack_prompts(source_dataset);
CREATE INDEX IF NOT EXISTS idx_prompts_difficulty ON attack_prompts(difficulty_estimate);
CREATE INDEX IF NOT EXISTS idx_techniques_technique ON prompt_techniques(technique);
CREATE INDEX IF NOT EXISTS idx_results_run ON eval_results(eval_run_id);
CREATE INDEX IF NOT EXISTS idx_results_prompt ON eval_results(prompt_id);
"""

# Lightweight migrations — ALTER TABLE for columns added after initial schema.
# Each migration is idempotent (safe to re-run on every startup).
_MIGRATIONS = [
    "ALTER TABLE eval_runs ADD COLUMN comparison_id TEXT",
]


async def init_db() -> None:
    """Create the database file and all tables/indexes, then apply migrations."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA_SQL)
        # Apply idempotent migrations (ignore "duplicate column" errors)
        for migration in _MIGRATIONS:
            try:
                await db.execute(migration)
            except Exception as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        await db.commit()
    logger.info("Database initialized at %s", settings.database_path)


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection]:
    """Async context manager for database connections."""
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
