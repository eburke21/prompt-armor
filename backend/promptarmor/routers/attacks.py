"""API endpoints for querying attack prompts."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from promptarmor.database import get_db
from promptarmor.models.attacks import AttackPromptDetail, PromptTechnique
from promptarmor.models.taxonomy import AttackListResponse

router = APIRouter(prefix="/api/v1", tags=["attacks"])


async def _get_techniques_for_prompts(
    db: Any, prompt_ids: list[str]
) -> dict[str, list[PromptTechnique]]:
    """Batch-fetch technique tags for a list of prompt IDs."""
    if not prompt_ids:
        return {}
    placeholders = ",".join("?" for _ in prompt_ids)
    rows = await (await db.execute(
        f"SELECT prompt_id, technique, confidence, classified_by "
        f"FROM prompt_techniques WHERE prompt_id IN ({placeholders})",
        prompt_ids,
    )).fetchall()
    result: dict[str, list[PromptTechnique]] = {}
    for r in rows:
        pid = str(r[0])
        result.setdefault(pid, []).append(
            PromptTechnique(
                technique=str(r[1]),
                confidence=float(r[2]),
                classified_by=str(r[3]),
            )
        )
    return result


@router.get("/attacks")
async def get_attacks(
    technique: str | None = None,
    source: str | None = None,
    difficulty_min: int | None = None,
    difficulty_max: int | None = None,
    is_injection: bool | None = None,
    language: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttackListResponse:
    """Query attack prompts with filters."""
    conditions: list[str] = []
    params: list[object] = []

    if technique:
        conditions.append(
            "ap.id IN (SELECT prompt_id FROM prompt_techniques WHERE technique = ?)"
        )
        params.append(technique)
    if source:
        conditions.append("ap.source_dataset = ?")
        params.append(source)
    if difficulty_min is not None:
        conditions.append("ap.difficulty_estimate >= ?")
        params.append(difficulty_min)
    if difficulty_max is not None:
        conditions.append("ap.difficulty_estimate <= ?")
        params.append(difficulty_max)
    if is_injection is not None:
        conditions.append("ap.is_injection = ?")
        params.append(is_injection)
    if language:
        conditions.append("ap.language = ?")
        params.append(language)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with get_db() as db:
        # Total count
        count_row = await (await db.execute(
            f"SELECT COUNT(*) FROM attack_prompts ap {where}", params
        )).fetchone()
        assert count_row is not None
        total = int(count_row[0])

        # Paginated results
        rows = await (await db.execute(
            f"SELECT * FROM attack_prompts ap {where} ORDER BY ap.id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )).fetchall()

        prompt_ids = [str(r[0]) for r in rows]  # id is first column
        techniques_map = await _get_techniques_for_prompts(db, prompt_ids)

    attacks = []
    for r in rows:
        pid = str(r[0])
        attacks.append(
            AttackPromptDetail(
                id=pid,
                source_dataset=str(r[1]),
                original_label=str(r[2]),
                is_injection=bool(r[3]),
                prompt_text=str(r[4]),
                language=str(r[5]),
                difficulty_estimate=r[6],
                character_count=int(r[7]),
                techniques=techniques_map.get(pid, []),
            )
        )

    return AttackListResponse(
        attacks=attacks,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/attacks/random")
async def get_random_attacks(
    count: int = Query(default=10, ge=1, le=100),
    technique: str | None = None,
    difficulty_min: int | None = None,
    difficulty_max: int | None = None,
) -> list[AttackPromptDetail]:
    """Return a random sample of attacks matching optional filters."""
    conditions: list[str] = ["ap.is_injection = 1"]
    params: list[object] = []

    if technique:
        conditions.append(
            "ap.id IN (SELECT prompt_id FROM prompt_techniques WHERE technique = ?)"
        )
        params.append(technique)
    if difficulty_min is not None:
        conditions.append("ap.difficulty_estimate >= ?")
        params.append(difficulty_min)
    if difficulty_max is not None:
        conditions.append("ap.difficulty_estimate <= ?")
        params.append(difficulty_max)

    where = f"WHERE {' AND '.join(conditions)}"

    async with get_db() as db:
        rows = await (await db.execute(
            f"SELECT * FROM attack_prompts ap {where} ORDER BY RANDOM() LIMIT ?",
            [*params, count],
        )).fetchall()

        prompt_ids = [str(r[0]) for r in rows]
        techniques_map = await _get_techniques_for_prompts(db, prompt_ids)

    return [
        AttackPromptDetail(
            id=str(r[0]),
            source_dataset=str(r[1]),
            original_label=str(r[2]),
            is_injection=bool(r[3]),
            prompt_text=str(r[4]),
            language=str(r[5]),
            difficulty_estimate=r[6],
            character_count=int(r[7]),
            techniques=techniques_map.get(str(r[0]), []),
        )
        for r in rows
    ]


@router.get("/attacks/{attack_id}")
async def get_attack(attack_id: str) -> AttackPromptDetail:
    """Return a single attack prompt with full technique detail."""
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM attack_prompts WHERE id = ?", (attack_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Attack prompt not found")

        techniques_map = await _get_techniques_for_prompts(db, [attack_id])

    return AttackPromptDetail(
        id=str(row[0]),
        source_dataset=str(row[1]),
        original_label=str(row[2]),
        is_injection=bool(row[3]),
        prompt_text=str(row[4]),
        language=str(row[5]),
        difficulty_estimate=row[6],
        character_count=int(row[7]),
        techniques=techniques_map.get(attack_id, []),
    )
