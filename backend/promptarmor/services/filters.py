"""Input filter implementations for the defense pipeline.

Each filter checks an incoming prompt and returns a FilterResult indicating
whether the prompt should be blocked before reaching the LLM.
"""

import abc
import logging
import re
from dataclasses import dataclass, field

import httpx

from promptarmor.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FilterResult:
    """Outcome of a single filter check."""

    blocked: bool
    filter_type: str
    score: float = 0.0
    reason: str | None = None
    warning: str | None = None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class InputFilter(abc.ABC):
    """Interface that every input filter must implement."""

    @abc.abstractmethod
    async def check(self, prompt: str) -> FilterResult:
        """Evaluate *prompt* and return a FilterResult."""


# ---------------------------------------------------------------------------
# Keyword blocklist filter
# ---------------------------------------------------------------------------


class KeywordBlocklistFilter(InputFilter):
    """Block prompts that contain any keyword from the configured list.

    Matching is **case-insensitive substring** — e.g. keyword "ignore previous"
    will match "Please IGNORE PREVIOUS instructions".
    """

    def __init__(self, keywords: list[str]) -> None:
        # Pre-compile patterns for efficient repeated matching.
        # re.escape ensures literal matching even if keywords contain regex chars.
        self.keywords = keywords
        self._patterns: list[re.Pattern[str]] = [
            re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords if kw
        ]

    async def check(self, prompt: str) -> FilterResult:
        for pattern in self._patterns:
            if pattern.search(prompt):
                return FilterResult(
                    blocked=True,
                    filter_type="keyword_blocklist",
                    score=1.0,
                    reason=f"Matched keyword: '{pattern.pattern}'",
                )
        return FilterResult(blocked=False, filter_type="keyword_blocklist")


# ---------------------------------------------------------------------------
# OpenAI Moderation API filter
# ---------------------------------------------------------------------------

_OPENAI_MODERATION_URL = "https://api.openai.com/v1/moderations"


class OpenAIModerationFilter(InputFilter):
    """Call the OpenAI Moderation API and block prompts above the threshold.

    Degrades gracefully: if the API is unreachable the prompt is **not** blocked
    (we add a warning instead).  This follows the principle that a monitoring
    layer should never silently break the happy path.
    """

    def __init__(
        self,
        threshold: float = 0.7,
        categories: list[str] | None = None,
    ) -> None:
        self.threshold = threshold
        self.categories = set(categories) if categories else None

    async def check(self, prompt: str) -> FilterResult:
        api_key = settings.openai_api_key
        if not api_key:
            return FilterResult(
                blocked=False,
                filter_type="openai_moderation",
                warning="OpenAI API key not configured — moderation filter skipped",
            )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    _OPENAI_MODERATION_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": "omni-moderation-latest", "input": prompt},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("OpenAI Moderation API HTTP error: %s", exc)
            return FilterResult(
                blocked=False,
                filter_type="openai_moderation",
                warning=f"OpenAI Moderation API returned {exc.response.status_code}",
            )
        except httpx.RequestError as exc:
            logger.warning("OpenAI Moderation API request error: %s", exc)
            return FilterResult(
                blocked=False,
                filter_type="openai_moderation",
                warning="OpenAI Moderation API unreachable — filter skipped",
            )

        # Parse response — find the highest-scoring relevant category
        results = data.get("results", [])
        if not results:
            return FilterResult(blocked=False, filter_type="openai_moderation")

        category_scores: dict[str, float] = results[0].get("category_scores", {})
        max_category = ""
        max_score = 0.0

        for cat, score in category_scores.items():
            # If user specified categories, only check those
            if self.categories and cat not in self.categories:
                continue
            if score > max_score:
                max_score = score
                max_category = cat

        if max_score >= self.threshold:
            return FilterResult(
                blocked=True,
                filter_type="openai_moderation",
                score=max_score,
                reason=(
                    f"Category '{max_category}' scored {max_score:.3f} "
                    f"(threshold {self.threshold})"
                ),
            )

        return FilterResult(
            blocked=False,
            filter_type="openai_moderation",
            score=max_score,
        )


# ---------------------------------------------------------------------------
# Composite input filter runner
# ---------------------------------------------------------------------------


@dataclass
class InputFilterRunner:
    """Run a list of input filters in sequence, short-circuiting on first block.

    Short-circuit is intentional: if the keyword filter blocks a prompt, we skip
    the OpenAI Moderation API call entirely — saving latency and API credits.
    """

    filters: list[InputFilter] = field(default_factory=list)

    async def run(self, prompt: str) -> FilterResult:
        """Execute all enabled filters. Return the first blocking result,
        or a 'passed' result if none block."""
        warnings: list[str] = []
        for f in self.filters:
            result = await f.check(prompt)
            if result.warning:
                warnings.append(result.warning)
            if result.blocked:
                return result

        # Nothing blocked — return a pass result, carrying any warnings
        return FilterResult(
            blocked=False,
            filter_type="none",
            warning="; ".join(warnings) if warnings else None,
        )
