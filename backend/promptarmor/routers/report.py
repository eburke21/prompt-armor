"""Report generation endpoint — uses Claude to produce red team assessment reports.

POST /api/v1/report/generate — generate a Markdown report from an eval run
"""

import json
import logging
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from promptarmor.config import settings
from promptarmor.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/report", tags=["report"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ReportGenerateRequest(BaseModel):
    """Request to generate a report for one or more eval runs."""

    eval_run_ids: list[str] = Field(min_length=1, max_length=3)


class ReportGenerateResponse(BaseModel):
    """Generated report response."""

    markdown: str
    eval_run_ids: list[str]
    model_used: str


# ---------------------------------------------------------------------------
# Claude prompt construction
# ---------------------------------------------------------------------------

REPORT_SYSTEM_PROMPT = """You are a senior AI security consultant writing a professional red team assessment report.

Your audience is a technical team that wants to understand how well their LLM defense configuration holds up against prompt injection attacks.

Write in clear, professional Markdown. Use specific numbers from the data. Be direct about weaknesses and actionable in recommendations.

Report structure:
1. **Executive Summary** — 2-3 sentences summarizing the overall defense posture, key block rate, and biggest risk
2. **Methodology** — Brief description of the test setup (attack set composition, defense layers tested)
3. **Findings by Technique** — For each technique tested, report the block rate, highlight any that fell below 50%, and explain the implications
4. **Defense Coverage Matrix** — A Markdown table showing which defense layers caught what. Highlight gaps.
5. **Notable Failures** — The most concerning individual prompts that bypassed all defenses. Quote the actual prompt text (truncated if long) and explain why it likely succeeded.
6. **Recommendations** — Prioritized, specific improvements. Reference the technique or layer that needs attention.

Formatting rules:
- Use ## for section headers
- Use tables for structured data (Markdown pipe tables)
- Use **bold** for emphasis on key metrics
- Use > blockquotes for notable prompt examples
- Keep the total report under 2000 words
- Be concise but thorough — every sentence should add value"""


def _build_report_prompt(
    runs: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> str:
    """Build the user prompt with eval data for Claude."""
    sections: list[str] = []

    for i, run in enumerate(runs):
        label = f"Config {chr(65 + i)}" if len(runs) > 1 else "Defense Config"
        config = run["defense_config"]
        stats = run.get("summary_stats", {})

        section = f"""### {label}

**System Prompt:** "{config.get('system_prompt', 'Not set')[:200]}"

**Input Filters:** {json.dumps(config.get('input_filters', []), indent=None)}
**Output Filters:** {json.dumps(config.get('output_filters', []), indent=None)}

**Results:**
- Total attacks: {stats.get('total_attacks', 'N/A')}
- Total benign: {stats.get('total_benign', 'N/A')}
- Attack block rate: {_fmt_pct(stats.get('attack_block_rate', 0))}
- False positive rate: {_fmt_pct(stats.get('false_positive_rate', 0))}

**By Technique:**
{_format_technique_table(stats.get('by_technique', {}))}

**By Defense Layer:**
{_format_layer_table(stats.get('by_layer', {}))}

**By Difficulty:**
{_format_difficulty_table(stats.get('by_difficulty', {}))}"""
        sections.append(section)

    prompt = f"""Generate a red team assessment report for the following eval run{"s" if len(runs) > 1 else ""}.

{"This is a comparison of " + str(len(runs)) + " defense configurations tested against the same attack set." if len(runs) > 1 else ""}

## Eval Data

{chr(10).join(sections)}

## Notable Failures (Injections That Bypassed All Defenses)

"""
    if failures:
        for j, f in enumerate(failures[:5], 1):
            prompt += f"""{j}. **Prompt ID:** {f.get('prompt_id', 'unknown')}
   **Text:** "{f.get('prompt_text', '')[:300]}"
   **Techniques:** {', '.join(f.get('techniques', []))}
   **Difficulty:** {f.get('difficulty_estimate', 'N/A')}

"""
    else:
        prompt += "No injections bypassed all defenses — the defense held at 100% block rate.\n"

    prompt += "\nPlease generate the full assessment report now."
    return prompt


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_technique_table(by_technique: dict[str, Any]) -> str:
    if not by_technique:
        return "No technique data available."
    lines = ["| Technique | Total | Blocked | Block Rate |", "| --- | ---: | ---: | ---: |"]
    for name, data in sorted(by_technique.items()):
        rate = data.get("rate", 0)
        lines.append(
            f"| {name} | {data.get('total', 0)} | {data.get('blocked', 0)} | {_fmt_pct(rate)} |"
        )
    return "\n".join(lines)


def _format_layer_table(by_layer: dict[str, Any]) -> str:
    if not by_layer:
        return "No layer data available."
    lines = ["| Layer | Blocked | Rate |", "| --- | ---: | ---: |"]
    for name, data in sorted(by_layer.items()):
        lines.append(
            f"| {name} | {data.get('blocked', 0)} | {_fmt_pct(data.get('rate', 0))} |"
        )
    return "\n".join(lines)


def _format_difficulty_table(by_difficulty: dict[str, Any]) -> str:
    if not by_difficulty:
        return "No difficulty data available."
    lines = ["| Difficulty | Total | Blocked | Block Rate |", "| --- | ---: | ---: | ---: |"]
    for level, data in sorted(by_difficulty.items(), key=lambda x: int(x[0])):
        lines.append(
            f"| Level {level} | {data.get('total', 0)} | {data.get('blocked', 0)} | "
            f"{_fmt_pct(data.get('rate', 0))} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# POST /api/v1/report/generate
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate_report(body: ReportGenerateRequest) -> ReportGenerateResponse:
    """Generate a red team assessment report using Claude."""

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured — report generation unavailable",
        )

    # --- Fetch eval runs and scorecards ---
    runs: list[dict[str, Any]] = []
    async with get_db() as db:
        for run_id in body.eval_run_ids:
            cursor = await db.execute(
                """
                SELECT id, status, defense_config, attack_set_config,
                       total_prompts, completed_prompts, summary_stats
                FROM eval_runs WHERE id = ?
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
            if row["status"] not in ("completed", "partial"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Run {run_id} is not completed (status: {row['status']})",
                )

            run_data: dict[str, Any] = {
                "id": row["id"],
                "defense_config": json.loads(row["defense_config"]),
                "attack_set_config": json.loads(row["attack_set_config"]),
                "summary_stats": json.loads(row["summary_stats"]) if row["summary_stats"] else {},
            }
            runs.append(run_data)

        # --- Fetch notable failures (injections that succeeded) ---
        failures: list[dict[str, Any]] = []
        for run_id in body.eval_run_ids:
            cursor = await db.execute(
                """
                SELECT er.prompt_id, ap.prompt_text, ap.difficulty_estimate,
                       er.injection_succeeded, er.blocked_by
                FROM eval_results er
                JOIN attack_prompts ap ON er.prompt_id = ap.id
                WHERE er.eval_run_id = ?
                  AND er.is_injection = 1
                  AND er.injection_succeeded = 1
                ORDER BY ap.difficulty_estimate DESC
                LIMIT 5
                """,
                (run_id,),
            )
            rows = await cursor.fetchall()
            for r in rows:
                # Also fetch techniques for this prompt
                tech_cursor = await db.execute(
                    "SELECT technique FROM prompt_techniques WHERE prompt_id = ?",
                    (r["prompt_id"],),
                )
                tech_rows = await tech_cursor.fetchall()
                techniques = [t["technique"] for t in tech_rows]

                failures.append({
                    "prompt_id": r["prompt_id"],
                    "prompt_text": r["prompt_text"],
                    "difficulty_estimate": r["difficulty_estimate"],
                    "techniques": techniques,
                })

    # --- Build prompt and call Claude ---
    user_prompt = _build_report_prompt(runs, failures)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        model = "claude-sonnet-4-20250514"

        message = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=REPORT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        report_text = ""
        for block in message.content:
            if block.type == "text":
                report_text += block.text

        logger.info(
            "Report generated for runs %s (%d tokens used)",
            body.eval_run_ids,
            message.usage.output_tokens,
        )

        return ReportGenerateResponse(
            markdown=report_text,
            eval_run_ids=body.eval_run_ids,
            model_used=model,
        )

    except anthropic.APIError as exc:
        logger.exception("Claude API error during report generation: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Claude API error: {exc}",
        ) from exc
