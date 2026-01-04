"""Attack set selection for eval runs.

Selects a balanced mix of injection and benign prompts from the database,
with proportional difficulty sampling and configurable benign mixing ratio.
"""

import logging
import math
import random
from dataclasses import dataclass

import aiosqlite

from promptarmor.database import get_db
from promptarmor.models.evals import AttackSetConfig

logger = logging.getLogger(__name__)


@dataclass
class SelectedPrompt:
    """A prompt selected for an eval run, with metadata."""

    id: str
    prompt_text: str
    is_injection: bool
    source_dataset: str
    difficulty_estimate: int
    techniques: list[str]


async def select_attacks(config: AttackSetConfig) -> list[SelectedPrompt]:
    """Select an attack set based on the provided configuration.

    Strategy:
    1. Query injection prompts matching technique/difficulty filters
    2. Sample proportionally by difficulty to maintain distribution
    3. Add benign prompts at the configured ratio (minimum 20%)
    4. Shuffle the final list so benign/attack are interleaved

    Returns a list of SelectedPrompt objects ready for the eval runner.
    """
    async with get_db() as db:
        # --- 1. Fetch injection prompts ---
        injection_prompts = await _fetch_injection_prompts(db, config)

        # --- 2. Proportional difficulty sampling ---
        attack_count = config.count
        if config.include_benign:
            # Reserve slots for benign prompts
            benign_ratio = max(config.benign_ratio, 0.2)  # Enforce minimum 20%
            attack_count = math.ceil(config.count * (1 - benign_ratio))

        sampled_attacks = _sample_proportional(injection_prompts, attack_count)

        # --- 3. Fetch and add benign prompts ---
        prompts: list[SelectedPrompt] = list(sampled_attacks)
        if config.include_benign:
            benign_count = config.count - len(prompts)
            if benign_count > 0:
                benign_prompts = await _fetch_benign_prompts(db, benign_count)
                prompts.extend(benign_prompts)

        # --- 4. Fetch technique tags for all selected prompts ---
        prompt_ids = [p.id for p in prompts]
        technique_map = await _fetch_techniques(db, prompt_ids)
        for p in prompts:
            p.techniques = technique_map.get(p.id, [])

    # --- 5. Shuffle ---
    random.shuffle(prompts)

    logger.info(
        "Selected %d prompts: %d attacks, %d benign",
        len(prompts),
        sum(1 for p in prompts if p.is_injection),
        sum(1 for p in prompts if not p.is_injection),
    )

    return prompts


async def _fetch_injection_prompts(
    db: aiosqlite.Connection,
    config: AttackSetConfig,
) -> list[SelectedPrompt]:
    """Fetch injection prompts matching the config filters."""
    conditions = ["ap.is_injection = 1"]
    params: list[object] = []

    # Difficulty range filter
    if config.difficulty_range and len(config.difficulty_range) == 2:
        conditions.append("ap.difficulty_estimate >= ?")
        params.append(config.difficulty_range[0])
        conditions.append("ap.difficulty_estimate <= ?")
        params.append(config.difficulty_range[1])

    # Technique filter — join against prompt_techniques
    if config.techniques:
        placeholders = ",".join("?" for _ in config.techniques)
        subquery = f"SELECT prompt_id FROM prompt_techniques WHERE technique IN ({placeholders})"
        conditions.append(f"ap.id IN ({subquery})")
        params.extend(config.techniques)

    where = " AND ".join(conditions)
    query = f"""
        SELECT ap.id, ap.prompt_text, ap.is_injection, ap.source_dataset,
               COALESCE(ap.difficulty_estimate, 1) as difficulty_estimate
        FROM attack_prompts ap
        WHERE {where}
    """

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    return [
        SelectedPrompt(
            id=row["id"],
            prompt_text=row["prompt_text"],
            is_injection=bool(row["is_injection"]),
            source_dataset=row["source_dataset"],
            difficulty_estimate=row["difficulty_estimate"],
            techniques=[],
        )
        for row in rows
    ]


async def _fetch_benign_prompts(
    db: aiosqlite.Connection,
    count: int,
) -> list[SelectedPrompt]:
    """Fetch a random sample of benign prompts."""
    cursor = await db.execute(
        """
        SELECT id, prompt_text, is_injection, source_dataset,
               COALESCE(difficulty_estimate, 1) as difficulty_estimate
        FROM attack_prompts
        WHERE is_injection = 0
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (count,),
    )
    rows = await cursor.fetchall()

    return [
        SelectedPrompt(
            id=row["id"],
            prompt_text=row["prompt_text"],
            is_injection=False,
            source_dataset=row["source_dataset"],
            difficulty_estimate=row["difficulty_estimate"],
            techniques=[],
        )
        for row in rows
    ]


async def _fetch_techniques(
    db: aiosqlite.Connection,
    prompt_ids: list[str],
) -> dict[str, list[str]]:
    """Batch-fetch technique tags for a set of prompt IDs."""
    if not prompt_ids:
        return {}

    placeholders = ",".join("?" for _ in prompt_ids)
    cursor = await db.execute(
        f"SELECT prompt_id, technique FROM prompt_techniques WHERE prompt_id IN ({placeholders})",
        prompt_ids,
    )
    rows = await cursor.fetchall()

    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["prompt_id"], []).append(row["technique"])
    return result


def _sample_proportional(
    prompts: list[SelectedPrompt],
    target_count: int,
) -> list[SelectedPrompt]:
    """Sample prompts proportionally by difficulty level.

    If we have 60% difficulty-1 and 40% difficulty-3 in the full set,
    the sample will maintain that proportion.
    """
    if len(prompts) <= target_count:
        return prompts

    # Group by difficulty
    by_difficulty: dict[int, list[SelectedPrompt]] = {}
    for p in prompts:
        by_difficulty.setdefault(p.difficulty_estimate, []).append(p)

    total = len(prompts)
    sampled: list[SelectedPrompt] = []

    for _diff_level, group in sorted(by_difficulty.items()):
        # Proportional allocation: (group size / total) * target
        allocation = max(1, round(len(group) / total * target_count))
        # Don't exceed group size
        allocation = min(allocation, len(group))
        sampled.extend(random.sample(group, allocation))

    # Trim if we over-allocated due to rounding, or pad if under
    if len(sampled) > target_count:
        sampled = random.sample(sampled, target_count)
    elif len(sampled) < target_count:
        # Add more from any remaining unsampled prompts
        sampled_ids = {p.id for p in sampled}
        remaining = [p for p in prompts if p.id not in sampled_ids]
        extra = min(target_count - len(sampled), len(remaining))
        if extra > 0:
            sampled.extend(random.sample(remaining, extra))

    return sampled
