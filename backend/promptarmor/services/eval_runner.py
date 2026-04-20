"""Evaluation orchestrator — the brain of the defense pipeline.

Runs attack prompts through: input filters → Claude LLM → output filters → scoring.
Yields SSE-compatible events as each prompt is processed.
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from promptarmor.config import settings
from promptarmor.database import get_db
from promptarmor.models.defenses import DefenseConfig
from promptarmor.models.evals import EvalResult
from promptarmor.services.attack_selector import SelectedPrompt
from promptarmor.services.filters import (
    InputFilterRunner,
    KeywordBlocklistFilter,
    OpenAIModerationFilter,
)
from promptarmor.services.llm_target import execute_against_target
from promptarmor.services.output_filters import (
    OutputFilterRunner,
    SecretLeakDetector,
)
from promptarmor.services.scoring import (
    classify_injection_success,
    compute_scorecard_with_difficulty,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSE event types
# ---------------------------------------------------------------------------


@dataclass
class RunEvent:
    """An event emitted during run execution, sent to the client via SSE."""

    event: str  # "progress" | "result" | "complete" | "error"
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Format as an SSE message string."""
        return json.dumps(self.data)


# ---------------------------------------------------------------------------
# Filter construction from defense config
# ---------------------------------------------------------------------------


def _build_input_filter_runner(config: DefenseConfig) -> InputFilterRunner:
    """Construct an InputFilterRunner from the defense config's input_filters."""
    from promptarmor.services.filters import InputFilter as InputFilterBase

    filters: list[InputFilterBase] = []
    for f in config.input_filters:
        if not f.enabled:
            continue
        if f.type == "keyword_blocklist":
            filters.append(KeywordBlocklistFilter(keywords=f.keywords))
        elif f.type == "openai_moderation":
            filters.append(
                OpenAIModerationFilter(
                    threshold=f.threshold,
                    categories=f.categories,
                )
            )
    return InputFilterRunner(filters=filters)


def _build_output_filter_runner(config: DefenseConfig) -> OutputFilterRunner:
    """Construct an OutputFilterRunner from the defense config's output_filters."""
    from promptarmor.services.output_filters import OutputFilter as OutputFilterBase

    filters: list[OutputFilterBase] = []
    for f in config.output_filters:
        if not f.enabled:
            continue
        if f.type == "secret_leak_detector":
            filters.append(
                SecretLeakDetector(
                    secrets=f.secrets,
                    patterns=f.patterns,
                )
            )
    return OutputFilterRunner(filters=filters)


# ---------------------------------------------------------------------------
# Run orchestrator
# ---------------------------------------------------------------------------


async def run_evaluation(
    run_id: str,
    defense_config: DefenseConfig,
    prompts: list[SelectedPrompt],
) -> AsyncGenerator[RunEvent, None]:
    """Run the full defense pipeline for each prompt, yielding SSE events.

    This is the core loop that the SSE endpoint iterates over.
    Processes prompts **sequentially** to avoid rate limit complexity.
    """
    total = len(prompts)
    results: list[EvalResult] = []
    failed_count = 0
    consecutive_failures = 0
    aborted_reason: str | None = None

    input_runner = _build_input_filter_runner(defense_config)
    output_runner = _build_output_filter_runner(defense_config)

    # Build lookup maps for scorecard
    technique_map: dict[str, list[str]] = {p.id: p.techniques for p in prompts}
    difficulty_map: dict[str, int] = {p.id: p.difficulty_estimate for p in prompts}

    run_deadline = time.monotonic() + settings.run_deadline_seconds
    failure_threshold = settings.max_consecutive_prompt_failures

    for idx, prompt in enumerate(prompts):
        # --- Deadline check: long Anthropic outage or stalled prompt ---
        if time.monotonic() > run_deadline:
            aborted_reason = (
                f"Run exceeded {settings.run_deadline_seconds}s deadline — "
                f"aborted after {idx}/{total} prompts."
            )
            logger.warning(aborted_reason)
            yield RunEvent(
                event="error",
                data={"message": aborted_reason, "aborted": True},
            )
            break

        try:
            result = await _process_single_prompt(
                run_id=run_id,
                prompt=prompt,
                defense_config=defense_config,
                input_runner=input_runner,
                output_runner=output_runner,
            )
            results.append(result)
            consecutive_failures = 0

            # Persist the result to the database
            await _store_result(result)

            # Update progress counter
            await _update_run_progress(run_id, idx + 1)

            # Yield progress event
            yield RunEvent(
                event="progress",
                data={
                    "completed": idx + 1,
                    "total": total,
                    "current_prompt_id": prompt.id,
                },
            )

            # Yield result event
            yield RunEvent(
                event="result",
                data={
                    "prompt_id": prompt.id,
                    "prompt_text": prompt.prompt_text[:200],
                    "is_injection": prompt.is_injection,
                    "blocked": result.input_filter_blocked or result.output_filter_blocked
                    or result.blocked_by == "llm_refused",
                    "blocked_by": result.blocked_by,
                    "input_filter_blocked": result.input_filter_blocked,
                    "input_filter_type": result.input_filter_type,
                    "output_filter_blocked": result.output_filter_blocked,
                    "output_filter_type": result.output_filter_type,
                    "injection_succeeded": result.injection_succeeded,
                    "llm_latency_ms": result.llm_latency_ms,
                    "techniques": prompt.techniques,
                    "difficulty": prompt.difficulty_estimate,
                },
            )

        except Exception as exc:
            logger.exception("Error processing prompt %s: %s", prompt.id, exc)
            failed_count += 1
            consecutive_failures += 1
            yield RunEvent(
                event="error",
                data={
                    "message": f"Error processing prompt: {exc}",
                    "prompt_id": prompt.id,
                },
            )
            # --- Circuit breaker: too many back-to-back failures ---
            if consecutive_failures >= failure_threshold:
                aborted_reason = (
                    f"Aborted after {consecutive_failures} consecutive "
                    f"per-prompt failures — check Anthropic API health."
                )
                logger.error(aborted_reason)
                yield RunEvent(
                    event="error",
                    data={"message": aborted_reason, "aborted": True},
                )
                break

    # --- Compute and store scorecard ---
    scorecard = compute_scorecard_with_difficulty(
        eval_run_id=run_id,
        results=results,
        technique_map=technique_map,
        difficulty_map=difficulty_map,
    )
    scorecard.failed_attacks = failed_count

    await _store_scorecard(run_id, scorecard, aborted=aborted_reason is not None)

    yield RunEvent(
        event="complete",
        data={
            "eval_run_id": run_id,
            "scorecard": scorecard.model_dump(),
            "failed_count": failed_count,
            "aborted": aborted_reason is not None,
            "aborted_reason": aborted_reason,
        },
    )


# ---------------------------------------------------------------------------
# Single prompt processing
# ---------------------------------------------------------------------------


async def _process_single_prompt(
    run_id: str,
    prompt: SelectedPrompt,
    defense_config: DefenseConfig,
    input_runner: InputFilterRunner,
    output_runner: OutputFilterRunner,
) -> EvalResult:
    """Run one prompt through the full pipeline and return an EvalResult."""
    result_id = str(uuid.uuid4())

    # --- Stage 1: Input filter ---
    input_result = await input_runner.run(prompt.prompt_text)

    if input_result.blocked:
        return EvalResult(
            id=result_id,
            eval_run_id=run_id,
            prompt_id=prompt.id,
            is_injection=prompt.is_injection,
            input_filter_blocked=True,
            input_filter_type=input_result.filter_type,
            input_filter_score=input_result.score,
            blocked_by="input_filter",
        )

    # --- Stage 2: LLM execution ---
    llm_result = await execute_against_target(
        system_prompt=defense_config.system_prompt,
        attack_prompt=prompt.prompt_text,
    )

    if llm_result.error:
        return EvalResult(
            id=result_id,
            eval_run_id=run_id,
            prompt_id=prompt.id,
            is_injection=prompt.is_injection,
            llm_response=f"[ERROR] {llm_result.error}",
            llm_latency_ms=llm_result.latency_ms,
            blocked_by=None,
        )

    # --- Stage 3: Output filter ---
    output_result = await output_runner.run(prompt.prompt_text, llm_result.response_text)

    if output_result.blocked:
        return EvalResult(
            id=result_id,
            eval_run_id=run_id,
            prompt_id=prompt.id,
            is_injection=prompt.is_injection,
            llm_response=llm_result.response_text,
            llm_latency_ms=llm_result.latency_ms,
            output_filter_blocked=True,
            output_filter_type=output_result.filter_type,
            output_filter_score=output_result.score,
            blocked_by="output_filter",
        )

    # --- Stage 4: Injection success classification ---
    injection_score = classify_injection_success(
        attack_prompt=prompt.prompt_text,
        llm_response=llm_result.response_text,
        is_injection=prompt.is_injection,
    )

    blocked_by: str | None = None
    if prompt.is_injection and injection_score.succeeded is False:
        blocked_by = "llm_refused"

    return EvalResult(
        id=result_id,
        eval_run_id=run_id,
        prompt_id=prompt.id,
        is_injection=prompt.is_injection,
        llm_response=llm_result.response_text,
        llm_latency_ms=llm_result.latency_ms,
        injection_succeeded=injection_score.succeeded,
        blocked_by=blocked_by,
        semantic_eval_score=injection_score.confidence,
    )


# ---------------------------------------------------------------------------
# Database persistence helpers
# ---------------------------------------------------------------------------


async def _store_result(result: EvalResult) -> None:
    """Persist a single result to the database."""
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO eval_results (
                id, eval_run_id, prompt_id, is_injection,
                input_filter_blocked, input_filter_type, input_filter_score,
                llm_response, llm_latency_ms,
                output_filter_blocked, output_filter_type, output_filter_score,
                injection_succeeded, blocked_by, semantic_eval_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.id,
                result.eval_run_id,
                result.prompt_id,
                result.is_injection,
                result.input_filter_blocked,
                result.input_filter_type,
                result.input_filter_score,
                result.llm_response,
                result.llm_latency_ms,
                result.output_filter_blocked,
                result.output_filter_type,
                result.output_filter_score,
                result.injection_succeeded,
                result.blocked_by,
                result.semantic_eval_score,
            ),
        )
        await db.commit()


async def _update_run_progress(run_id: str, completed: int) -> None:
    """Update the completed_prompts counter on the run."""
    async with get_db() as db:
        await db.execute(
            "UPDATE eval_runs SET completed_prompts = ? WHERE id = ?",
            (completed, run_id),
        )
        await db.commit()


async def _store_scorecard(
    run_id: str, scorecard: Any, *, aborted: bool = False
) -> None:
    """Store the final scorecard and mark the run's terminal status.

    A run that hits the deadline or circuit breaker is marked 'partial' so
    the UI can distinguish "all prompts processed" from "we gave up early."
    """
    status = "partial" if aborted else "completed"
    async with get_db() as db:
        await db.execute(
            "UPDATE eval_runs SET status = ?, summary_stats = ? WHERE id = ?",
            (status, json.dumps(scorecard.model_dump()), run_id),
        )
        await db.commit()
