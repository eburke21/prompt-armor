"""Claude API target executor for the defense pipeline.

Sends (system_prompt, attack_prompt) to Claude and returns the response.
Implements retry with exponential backoff and prompt truncation.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from promptarmor.config import settings

logger = logging.getLogger(__name__)

_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 1024
_MAX_PROMPT_CHARS = 4000
_MAX_RETRIES = 3
_BASE_DELAY_S = 1.0


@dataclass
class LLMResult:
    """Outcome of sending one prompt to the target LLM."""

    response_text: str
    latency_ms: int
    error: str | None = None
    truncated: bool = False


async def execute_against_target(
    system_prompt: str,
    attack_prompt: str,
) -> LLMResult:
    """Send *system_prompt* + *attack_prompt* to Claude and return the response.

    Retries up to 3 times on transient errors (429, 5xx) with exponential backoff.
    Returns an error result (not an exception) on permanent failure so the pipeline
    can continue processing the remaining prompts.
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        return LLMResult(
            response_text="",
            latency_ms=0,
            error="Anthropic API key not configured",
        )

    # Truncate long prompts to control token usage
    truncated = False
    if len(attack_prompt) > _MAX_PROMPT_CHARS:
        attack_prompt = attack_prompt[:_MAX_PROMPT_CHARS] + "\n[TRUNCATED]"
        truncated = True

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": _MODEL,
        "max_tokens": _MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": attack_prompt}],
    }

    last_error: str | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    _ANTHROPIC_MESSAGES_URL,
                    headers=headers,
                    json=payload,
                )
            latency_ms = int((time.monotonic() - start) * 1000)

            # Rate limit — respect Retry-After header
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("retry-after", _BASE_DELAY_S * (2**attempt)))
                logger.warning(
                    "Claude rate limit hit (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                last_error = f"Rate limited (429) on attempt {attempt + 1}"
                continue

            # Server error — retry with backoff
            if resp.status_code >= 500:
                delay = _BASE_DELAY_S * (2**attempt)
                logger.warning(
                    "Claude server error %d (attempt %d/%d), retrying in %.1fs",
                    resp.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
                last_error = f"Server error {resp.status_code} on attempt {attempt + 1}"
                continue

            # Client error (4xx, not 429) — don't retry
            if resp.status_code >= 400:
                error_body = resp.text[:500]
                logger.error("Claude client error %d: %s", resp.status_code, error_body)
                return LLMResult(
                    response_text="",
                    latency_ms=latency_ms,
                    error=f"Claude API error {resp.status_code}: {error_body}",
                    truncated=truncated,
                )

            # Success — extract the text from the response
            data = resp.json()
            content_blocks = data.get("content", [])
            text_parts = [
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            ]
            response_text = "\n".join(text_parts)

            return LLMResult(
                response_text=response_text,
                latency_ms=latency_ms,
                truncated=truncated,
            )

        except httpx.RequestError as exc:
            delay = _BASE_DELAY_S * (2**attempt)
            logger.warning(
                "Claude request error (attempt %d/%d): %s, retrying in %.1fs",
                attempt + 1,
                _MAX_RETRIES,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            last_error = f"Request error: {exc}"

    # Exhausted all retries
    return LLMResult(
        response_text="",
        latency_ms=0,
        error=f"Failed after {_MAX_RETRIES} attempts: {last_error}",
        truncated=truncated,
    )
