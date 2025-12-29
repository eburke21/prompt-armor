"""Models for the taxonomy browser API responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from promptarmor.models.attacks import AttackPromptDetail


class TechniqueInfo(BaseModel):
    """A technique in the taxonomy with aggregate stats."""

    id: str
    name: str
    description: str
    example_count: int
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)


class DatasetInfo(BaseModel):
    """Summary info about a source dataset."""

    id: str
    name: str
    count: int
    license: str


class TaxonomyResponse(BaseModel):
    """Response for GET /api/v1/taxonomy."""

    techniques: list[TechniqueInfo]
    total_prompts: int
    total_injections: int
    total_benign: int
    datasets: list[DatasetInfo]


class AttackListResponse(BaseModel):
    """Paginated response for GET /api/v1/attacks."""

    attacks: list[AttackPromptDetail]
    total: int
    limit: int
    offset: int
