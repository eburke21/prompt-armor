"""Output filter implementations for the defense pipeline.

Output filters inspect the LLM response (and optionally the original prompt)
to detect secret leaks, compliance violations, etc.
"""

import abc
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OutputFilterResult:
    """Outcome of a single output filter check."""

    blocked: bool
    filter_type: str
    score: float = 0.0
    reason: str | None = None


class OutputFilter(abc.ABC):
    """Interface that every output filter must implement."""

    @abc.abstractmethod
    async def check(self, prompt: str, response: str) -> OutputFilterResult:
        """Evaluate *response* (given *prompt* context) and return a result."""


# ---------------------------------------------------------------------------
# Secret leak detector
# ---------------------------------------------------------------------------


class SecretLeakDetector(OutputFilter):
    """Detect if the LLM leaked any configured secrets in its response.

    Two detection strategies:
    1. Exact string matching — case-insensitive check for literal secret values
    2. Regex pattern matching — for flexible patterns like `(?i)the password is \\w+`

    Invalid regex patterns are logged and skipped rather than crashing the pipeline.
    """

    def __init__(
        self,
        secrets: list[str] | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        self.secrets = secrets or []
        self._patterns: list[re.Pattern[str]] = []
        for p in patterns or []:
            try:
                self._patterns.append(re.compile(p, re.IGNORECASE))
            except re.error as exc:
                logger.warning("Invalid output filter regex '%s': %s — skipping", p, exc)

    async def check(self, prompt: str, response: str) -> OutputFilterResult:
        response_lower = response.lower()

        # Check exact secret strings (case-insensitive)
        for secret in self.secrets:
            if secret.lower() in response_lower:
                return OutputFilterResult(
                    blocked=True,
                    filter_type="secret_leak_detector",
                    score=1.0,
                    reason=f"Secret value detected in response: '{secret[:20]}...'",
                )

        # Check regex patterns
        for pattern in self._patterns:
            if pattern.search(response):
                return OutputFilterResult(
                    blocked=True,
                    filter_type="secret_leak_detector",
                    score=1.0,
                    reason=f"Pattern matched in response: '{pattern.pattern[:40]}'",
                )

        return OutputFilterResult(
            blocked=False,
            filter_type="secret_leak_detector",
        )


# ---------------------------------------------------------------------------
# Composite output filter runner
# ---------------------------------------------------------------------------


@dataclass
class OutputFilterRunner:
    """Run a list of output filters in sequence, short-circuiting on first block."""

    filters: list[OutputFilter] = field(default_factory=list)

    async def run(self, prompt: str, response: str) -> OutputFilterResult:
        for f in self.filters:
            result = await f.check(prompt, response)
            if result.blocked:
                return result

        return OutputFilterResult(blocked=False, filter_type="none")
