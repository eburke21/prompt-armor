"""API endpoints for the attack taxonomy browser."""

from fastapi import APIRouter

from promptarmor.database import get_db
from promptarmor.ingestion.constants import DATASET_METADATA, TECHNIQUE_METADATA
from promptarmor.models.taxonomy import DatasetInfo, TaxonomyResponse, TechniqueInfo

router = APIRouter(prefix="/api/v1", tags=["taxonomy"])


@router.get("/taxonomy")
async def get_taxonomy() -> TaxonomyResponse:
    """Return the full attack technique taxonomy with counts and distributions."""
    async with get_db() as db:
        # Total counts
        row = await (await db.execute(
            "SELECT COUNT(*), SUM(is_injection), SUM(NOT is_injection) FROM attack_prompts"
        )).fetchone()
        assert row is not None
        total_prompts, total_injections, total_benign = int(row[0]), int(row[1]), int(row[2])

        # Technique counts
        tech_rows = await (await db.execute(
            "SELECT technique, COUNT(*) FROM prompt_techniques GROUP BY technique"
        )).fetchall()
        tech_counts: dict[str, int] = {str(r[0]): int(r[1]) for r in tech_rows}

        # Difficulty distribution per technique
        diff_rows = await (await db.execute(
            """SELECT pt.technique, ap.difficulty_estimate, COUNT(*)
               FROM prompt_techniques pt
               JOIN attack_prompts ap ON pt.prompt_id = ap.id
               WHERE ap.difficulty_estimate IS NOT NULL
               GROUP BY pt.technique, ap.difficulty_estimate"""
        )).fetchall()
        diff_dist: dict[str, dict[str, int]] = {}
        for r in diff_rows:
            tech = str(r[0])
            diff = str(r[1])
            count = int(r[2])
            diff_dist.setdefault(tech, {})[diff] = count

        # Dataset counts
        ds_rows = await (await db.execute(
            "SELECT source_dataset, COUNT(*) FROM attack_prompts GROUP BY source_dataset"
        )).fetchall()

    # Build technique info list
    techniques = []
    for tech_id in sorted(tech_counts.keys()):
        meta = TECHNIQUE_METADATA.get(tech_id, {"name": tech_id, "description": ""})
        techniques.append(
            TechniqueInfo(
                id=tech_id,
                name=meta["name"],
                description=meta["description"],
                example_count=tech_counts[tech_id],
                difficulty_distribution=diff_dist.get(tech_id, {}),
            )
        )

    # Build dataset info list
    datasets = []
    for r in ds_rows:
        ds_id = str(r[0])
        meta = DATASET_METADATA.get(ds_id, {"name": ds_id, "license": "Unknown"})
        datasets.append(
            DatasetInfo(
                id=ds_id,
                name=meta["name"],
                count=int(r[1]),
                license=meta["license"],
            )
        )

    return TaxonomyResponse(
        techniques=techniques,
        total_prompts=total_prompts,
        total_injections=total_injections,
        total_benign=total_benign,
        datasets=datasets,
    )
