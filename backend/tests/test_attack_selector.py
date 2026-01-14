"""Tests for attack set selection and proportional sampling."""

from promptarmor.services.attack_selector import SelectedPrompt, _sample_proportional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prompt(
    pid: str,
    is_injection: bool = True,
    difficulty: int = 1,
    techniques: list[str] | None = None,
) -> SelectedPrompt:
    return SelectedPrompt(
        id=pid,
        prompt_text=f"prompt-{pid}",
        is_injection=is_injection,
        source_dataset="test",
        difficulty_estimate=difficulty,
        techniques=techniques or [],
    )


# ---------------------------------------------------------------------------
# _sample_proportional
# ---------------------------------------------------------------------------


class TestSampleProportional:
    def test_returns_all_when_fewer_than_target(self) -> None:
        prompts = [_make_prompt(f"p{i}") for i in range(5)]
        result = _sample_proportional(prompts, 10)
        assert len(result) == 5

    def test_returns_exact_when_equal_to_target(self) -> None:
        prompts = [_make_prompt(f"p{i}") for i in range(10)]
        result = _sample_proportional(prompts, 10)
        assert len(result) == 10

    def test_samples_down_to_target(self) -> None:
        prompts = [_make_prompt(f"p{i}") for i in range(100)]
        result = _sample_proportional(prompts, 20)
        assert len(result) == 20

    def test_preserves_difficulty_distribution(self) -> None:
        """60 easy + 40 hard → sample of 20 should be roughly 12 easy + 8 hard."""
        prompts = [_make_prompt(f"easy-{i}", difficulty=1) for i in range(60)]
        prompts += [_make_prompt(f"hard-{i}", difficulty=5) for i in range(40)]

        result = _sample_proportional(prompts, 20)
        assert len(result) == 20

        easy_count = sum(1 for p in result if p.difficulty_estimate == 1)
        hard_count = sum(1 for p in result if p.difficulty_estimate == 5)
        # Allow some rounding variance but proportions should be roughly maintained
        assert easy_count >= 8, f"Expected >=8 easy prompts, got {easy_count}"
        assert hard_count >= 5, f"Expected >=5 hard prompts, got {hard_count}"

    def test_at_least_one_per_difficulty(self) -> None:
        """Each difficulty level should get at least 1 slot."""
        prompts = [_make_prompt("rare-1", difficulty=5)]
        prompts += [_make_prompt(f"common-{i}", difficulty=1) for i in range(99)]

        result = _sample_proportional(prompts, 10)
        difficulties = {p.difficulty_estimate for p in result}
        assert 5 in difficulties, "Rare difficulty level should still be represented"

    def test_empty_input(self) -> None:
        result = _sample_proportional([], 10)
        assert result == []

    def test_single_prompt(self) -> None:
        prompts = [_make_prompt("only")]
        result = _sample_proportional(prompts, 1)
        assert len(result) == 1

    def test_no_duplicates(self) -> None:
        prompts = [_make_prompt(f"p{i}", difficulty=(i % 3) + 1) for i in range(50)]
        result = _sample_proportional(prompts, 20)
        ids = [p.id for p in result]
        assert len(ids) == len(set(ids)), "Sample should not contain duplicates"


# ---------------------------------------------------------------------------
# SelectedPrompt dataclass
# ---------------------------------------------------------------------------


class TestSelectedPrompt:
    def test_create_injection(self) -> None:
        p = _make_prompt("test-1", is_injection=True, difficulty=3)
        assert p.is_injection is True
        assert p.difficulty_estimate == 3

    def test_create_benign(self) -> None:
        p = _make_prompt("test-2", is_injection=False)
        assert p.is_injection is False

    def test_techniques_default_empty(self) -> None:
        p = _make_prompt("test-3")
        assert p.techniques == []

    def test_techniques_assigned(self) -> None:
        p = _make_prompt("test-4", techniques=["instruction_override", "roleplay_exploit"])
        assert len(p.techniques) == 2
