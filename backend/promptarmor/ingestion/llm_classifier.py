"""LLM-assisted classifier for prompts that heuristics couldn't classify.

Sends batches of unclassified injection prompts to Claude for technique
classification. Respects a cap to control API costs.
"""

import json
import logging

import httpx

from promptarmor.config import settings
from promptarmor.models.attacks import AttackPrompt, PromptTechnique

logger = logging.getLogger(__name__)

_VALID_TECHNIQUES = {
    "instruction_override",
    "roleplay_exploit",
    "encoding_trick",
    "context_manipulation",
    "indirect_injection",
    "few_shot_poisoning",
    "output_format_exploit",
    "language_switch",
    "payload_splitting",
    "multi_turn_escalation",
}

_SYSTEM_PROMPT = """You are an expert in LLM prompt injection classification.
Given a list of prompts, classify each into one or more technique categories.

Valid categories:
- instruction_override: Direct "ignore previous instructions" attempts
- roleplay_exploit: Persona/character hijacking ("you are now DAN", "pretend you are")
- encoding_trick: Base64, ROT13, pig latin, morse code obfuscation
- context_manipulation: Fake system messages, delimiter injection
- indirect_injection: Payload hidden in "content to summarize/translate"
- few_shot_poisoning: Malicious examples in prompt
- output_format_exploit: Forcing specific output format to bypass filters
- language_switch: Switching languages to evade filters
- payload_splitting: Splitting malicious content across parts
- multi_turn_escalation: Gradual boundary-pushing

Respond with a JSON array. Each element:
{"index": <int>, "techniques": [{"technique": "<id>", "confidence": <float>}]}
Only include techniques that genuinely apply. If unsure, use lower confidence."""

_BATCH_SIZE = 20
_MAX_UNCLASSIFIED = 2000


async def classify_with_llm(
    prompts: list[tuple[int, AttackPrompt]],
) -> dict[str, list[PromptTechnique]]:
    """Send unclassified prompts to Claude for classification.

    Args:
        prompts: List of (index, prompt) tuples to classify.

    Returns:
        Dict mapping prompt_id to list of PromptTechnique.
    """
    if not settings.anthropic_api_key:
        logger.warning("No ANTHROPIC_API_KEY set — skipping LLM classification")
        return {}

    results: dict[str, list[PromptTechnique]] = {}
    capped = prompts[:_MAX_UNCLASSIFIED]
    logger.info("LLM-classifying %d prompts (capped from %d)", len(capped), len(prompts))

    async with httpx.AsyncClient(timeout=60.0) as client:
        for batch_start in range(0, len(capped), _BATCH_SIZE):
            batch = capped[batch_start : batch_start + _BATCH_SIZE]
            user_content = "\n\n".join(
                f"[{i}] {p.prompt_text[:500]}" for i, (_, p) in enumerate(batch)
            )

            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 2048,
                        "system": _SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_content}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["content"][0]["text"]

                # Extract JSON from response (handle markdown code blocks)
                json_text = text
                if "```" in text:
                    json_text = text.split("```")[1]
                    if json_text.startswith("json"):
                        json_text = json_text[4:]

                classifications = json.loads(json_text)
                for entry in classifications:
                    idx = int(entry["index"])
                    if 0 <= idx < len(batch):
                        _, prompt = batch[idx]
                        techniques = []
                        for t in entry.get("techniques", []):
                            tech_name = t.get("technique", "")
                            if tech_name in _VALID_TECHNIQUES:
                                techniques.append(
                                    PromptTechnique(
                                        technique=tech_name,
                                        confidence=float(t.get("confidence", 0.7)),
                                        classified_by="llm",
                                    )
                                )
                        if techniques:
                            results[prompt.id] = techniques

            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
                logger.warning("LLM classification batch failed: %s", e)
                continue

            logger.info(
                "  Batch %d-%d complete, %d classified so far",
                batch_start,
                batch_start + len(batch),
                len(results),
            )

    return results
