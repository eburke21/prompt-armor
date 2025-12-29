"""Models for evaluation runs, results, and scorecards."""

from pydantic import BaseModel, Field

from promptarmor.models.defenses import DefenseConfig


class AttackSetConfig(BaseModel):
    """Configuration for selecting an attack set."""

    techniques: list[str] = Field(default_factory=list)
    difficulty_range: list[int] = Field(default=[1, 5], min_length=2, max_length=2)
    count: int = Field(default=20, ge=1, le=200)
    include_benign: bool = True
    benign_ratio: float = Field(default=0.3, ge=0.0, le=1.0)


class EvalRunCreate(BaseModel):
    """Request body for starting a new eval run."""

    defense_config: DefenseConfig
    attack_set: AttackSetConfig


class EvalRunResponse(BaseModel):
    """Response when creating an eval run."""

    eval_run_id: str
    status: str = "pending"
    total_prompts: int
    stream_url: str


class EvalResult(BaseModel):
    """A single eval result for one prompt."""

    model_config = {"from_attributes": True}

    id: str
    eval_run_id: str
    prompt_id: str
    is_injection: bool
    input_filter_blocked: bool = False
    input_filter_type: str | None = None
    input_filter_score: float | None = None
    llm_response: str | None = None
    llm_latency_ms: int | None = None
    output_filter_blocked: bool = False
    output_filter_type: str | None = None
    output_filter_score: float | None = None
    injection_succeeded: bool | None = None
    blocked_by: str | None = None
    semantic_eval_score: float | None = None


# --- Scorecard models ---


class TechniqueScore(BaseModel):
    """Block rate for a single technique."""

    total: int
    blocked: int
    rate: float


class LayerScore(BaseModel):
    """Block count/rate for a defense layer."""

    blocked: int
    rate: float


class DifficultyScore(BaseModel):
    """Block rate at a single difficulty level."""

    total: int
    blocked: int
    rate: float


class Scorecard(BaseModel):
    """Aggregated results from an eval run."""

    eval_run_id: str
    total_attacks: int
    total_benign: int
    attack_block_rate: float
    false_positive_rate: float
    by_technique: dict[str, TechniqueScore] = Field(default_factory=dict)
    by_layer: dict[str, LayerScore] = Field(default_factory=dict)
    by_difficulty: dict[str, DifficultyScore] = Field(default_factory=dict)


class EvalRun(BaseModel):
    """An eval run with its current state."""

    model_config = {"from_attributes": True}

    id: str
    status: str
    defense_config: DefenseConfig
    attack_set_config: AttackSetConfig
    total_prompts: int
    completed_prompts: int = 0
    summary_stats: Scorecard | None = None
