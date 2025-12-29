"""Models for attack prompts and technique classification."""

from pydantic import BaseModel, Field


class PromptTechnique(BaseModel):
    """A technique tag assigned to a prompt."""

    technique: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    classified_by: str = "heuristic"


class AttackPrompt(BaseModel):
    """An attack prompt from the dataset."""

    model_config = {"from_attributes": True}

    id: str
    prompt_text: str
    source_dataset: str
    original_label: str
    is_injection: bool
    language: str = "en"
    difficulty_estimate: int | None = None
    character_count: int = 0


class AttackPromptDetail(AttackPrompt):
    """An attack prompt with its technique tags."""

    techniques: list[PromptTechnique] = Field(default_factory=list)


class SystemPrompt(BaseModel):
    """A system prompt (from SPML dataset or built-in)."""

    model_config = {"from_attributes": True}

    id: str
    source: str
    name: str | None = None
    prompt_text: str
    category: str | None = None
