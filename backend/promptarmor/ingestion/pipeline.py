"""Ingestion pipeline orchestrator — runs ingestors, deduplicates, writes to DB."""

import logging
from collections.abc import Callable

import aiosqlite

from promptarmor.config import settings
from promptarmor.database import init_db
from promptarmor.ingestion.base import DatasetIngestor
from promptarmor.models.attacks import AttackPrompt, PromptTechnique, SystemPrompt

logger = logging.getLogger(__name__)

ClassifierFn = Callable[[list[AttackPrompt]], list[tuple[str, list[PromptTechnique]]]]


async def run_pipeline(
    ingestors: list[DatasetIngestor],
    classifier_fn: ClassifierFn,
    sample: int | None = None,
    skip_llm: bool = True,
    verbose: bool = False,
) -> dict[str, int]:
    """Run the full ingestion pipeline.

    Returns summary stats dict.
    """
    await init_db()

    all_prompts: list[AttackPrompt] = []
    all_system_prompts: list[SystemPrompt] = []
    seen_prompt_ids: set[str] = set()
    stats: dict[str, int] = {
        "total_prompts": 0,
        "duplicates_skipped": 0,
        "injections": 0,
        "benign": 0,
    }

    # Phase 1: Download and normalize from each ingestor
    for ingestor in ingestors:
        name = ingestor.source_name
        logger.info("Downloading dataset: %s", name)
        ingestor.download(sample=sample)

        logger.info("Normalizing dataset: %s", name)
        prompts = ingestor.normalize()

        # Deduplicate by ID (deterministic from text+source)
        unique = []
        for p in prompts:
            if p.id not in seen_prompt_ids:
                seen_prompt_ids.add(p.id)
                unique.append(p)
            else:
                stats["duplicates_skipped"] += 1

        all_prompts.extend(unique)
        stats[f"{name}_count"] = len(unique)
        logger.info("  %s: %d unique prompts (of %d total)", name, len(unique), len(prompts))

        # Collect system prompts if the ingestor provides them
        sys_prompts = ingestor.get_system_prompts()
        if sys_prompts:
            all_system_prompts.extend(sys_prompts)
            logger.info("  %s: %d system prompts", name, len(sys_prompts))

    # Phase 2: Classify techniques
    logger.info("Classifying %d prompts...", len(all_prompts))
    classifications = classifier_fn(all_prompts)

    # Phase 3: Write to database
    logger.info("Writing to database at %s", settings.database_path)
    async with aiosqlite.connect(settings.database_path) as db:
        # Clear existing data for clean re-ingestion
        await db.execute("DELETE FROM prompt_techniques")
        await db.execute("DELETE FROM attack_prompts")
        await db.execute("DELETE FROM system_prompts")

        # Insert prompts
        for prompt in all_prompts:
            await db.execute(
                """INSERT OR REPLACE INTO attack_prompts
                   (id, source_dataset, original_label, is_injection, prompt_text,
                    language, difficulty_estimate, character_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prompt.id,
                    prompt.source_dataset,
                    prompt.original_label,
                    prompt.is_injection,
                    prompt.prompt_text,
                    prompt.language,
                    prompt.difficulty_estimate,
                    prompt.character_count,
                ),
            )
            if prompt.is_injection:
                stats["injections"] += 1
            else:
                stats["benign"] += 1

        # Insert technique tags
        technique_count = 0
        for prompt_id, techniques in classifications:
            for tech in techniques:
                await db.execute(
                    """INSERT OR REPLACE INTO prompt_techniques
                       (prompt_id, technique, confidence, classified_by)
                       VALUES (?, ?, ?, ?)""",
                    (prompt_id, tech.technique, tech.confidence, tech.classified_by),
                )
                technique_count += 1

        # Insert system prompts
        for sp in all_system_prompts:
            await db.execute(
                """INSERT OR REPLACE INTO system_prompts
                   (id, source, name, prompt_text, category)
                   VALUES (?, ?, ?, ?, ?)""",
                (sp.id, sp.source, sp.name, sp.prompt_text, sp.category),
            )

        await db.commit()

    stats["total_prompts"] = len(all_prompts)
    stats["system_prompts"] = len(all_system_prompts)
    stats["technique_tags"] = technique_count

    return stats
