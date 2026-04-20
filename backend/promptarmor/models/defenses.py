"""Models for defense configurations (input/output filters)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# --- Input Filters ---


class KeywordBlocklistConfig(BaseModel):
    """Configuration for keyword-based input blocking."""

    type: Literal["keyword_blocklist"] = "keyword_blocklist"
    enabled: bool = True
    keywords: list[str] = Field(default_factory=list)


class OpenAIModerationConfig(BaseModel):
    """Configuration for OpenAI Moderation API input filter."""

    type: Literal["openai_moderation"] = "openai_moderation"
    enabled: bool = True
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    categories: list[str] = Field(default_factory=lambda: ["harassment", "violence", "illicit"])


InputFilter = Annotated[
    KeywordBlocklistConfig | OpenAIModerationConfig,
    Field(discriminator="type"),
]


# --- Output Filters ---


class SecretLeakDetectorConfig(BaseModel):
    """Configuration for output secret leak detection."""

    type: Literal["secret_leak_detector"] = "secret_leak_detector"
    enabled: bool = True
    secrets: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)


# Only one output filter variant exists today; restore an Annotated discriminated
# union (see InputFilter above) when a second variant is added.
type OutputFilter = SecretLeakDetectorConfig


# --- Composite Defense Config ---


class DefenseConfig(BaseModel):
    """Full defense configuration for an eval run."""

    system_prompt: str = ""
    input_filters: list[InputFilter] = Field(default_factory=list)
    output_filters: list[OutputFilter] = Field(default_factory=list)
