"""API endpoints for system prompts."""

from fastapi import APIRouter, HTTPException, Query

from promptarmor.database import get_db
from promptarmor.models.attacks import SystemPrompt

router = APIRouter(prefix="/api/v1", tags=["system-prompts"])


@router.get("/system-prompts")
async def get_system_prompts(
    source: str | None = None,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SystemPrompt]:
    """List system prompts, optionally filtered by source and category."""
    conditions: list[str] = []
    params: list[object] = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if category:
        conditions.append("category = ?")
        params.append(category)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with get_db() as db:
        rows = await (await db.execute(
            f"SELECT id, source, name, prompt_text, category "
            f"FROM system_prompts {where} ORDER BY source, name LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )).fetchall()

    return [
        SystemPrompt(
            id=str(r[0]),
            source=str(r[1]),
            name=r[2],
            prompt_text=str(r[3]),
            category=r[4],
        )
        for r in rows
    ]


@router.get("/system-prompts/{prompt_id}")
async def get_system_prompt(prompt_id: str) -> SystemPrompt:
    """Get a single system prompt."""
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT id, source, name, prompt_text, category FROM system_prompts WHERE id = ?",
            (prompt_id,),
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="System prompt not found")

    return SystemPrompt(
        id=str(row[0]),
        source=str(row[1]),
        name=row[2],
        prompt_text=str(row[3]),
        category=row[4],
    )
