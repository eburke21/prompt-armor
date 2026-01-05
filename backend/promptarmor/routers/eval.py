"""Evaluation run API endpoints with SSE streaming.

POST /api/v1/eval/run        — start a new run
GET  /api/v1/eval/run/{id}/stream — SSE stream of results
GET  /api/v1/eval/run/{id}   — run status + scorecard
GET  /api/v1/eval/run/{id}/results — paginated individual results
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from promptarmor.config import settings
from promptarmor.database import get_db
from promptarmor.middleware.rate_limit import (
    RateLimitExceeded,
    check_rate_limits,
    register_run_complete,
    register_run_start,
)
from promptarmor.models.evals import (
    EvalRunCreate,
    EvalRunResponse,
)
from promptarmor.services.attack_selector import select_attacks
from promptarmor.services.eval_runner import RunEvent, run_evaluation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/eval", tags=["evaluation"])


# ---------------------------------------------------------------------------
# In-memory tracking for active runs
# ---------------------------------------------------------------------------

# Maps run_id → list of events already emitted (for late-joining SSE clients)
_run_event_logs: dict[str, list[RunEvent]] = {}

# Maps run_id → asyncio.Event signaling run completion
_run_complete_events: dict[str, asyncio.Event] = {}

# Maps run_id → asyncio.Queue for broadcasting to SSE clients
_run_queues: dict[str, asyncio.Queue[RunEvent | None]] = {}

# Set of background tasks — prevents garbage collection (RUF006)
_background_tasks: set[asyncio.Task[None]] = set()


# ---------------------------------------------------------------------------
# POST /api/v1/eval/run — Start a new evaluation run
# ---------------------------------------------------------------------------


@router.post("/run", status_code=201)
async def start_eval_run(body: EvalRunCreate, request: Request) -> EvalRunResponse:
    """Create a new evaluation run and kick off processing."""

    # --- Rate limiting ---
    client_ip = request.client.host if request.client else "unknown"
    try:
        check_rate_limits(client_ip)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=exc.message,
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    # --- Validate config ---
    if body.attack_set.count > settings.max_prompts_per_run:
        raise HTTPException(
            status_code=400,
            detail=f"Max {settings.max_prompts_per_run} prompts per run",
        )

    # --- Select attack prompts ---
    prompts = await select_attacks(body.attack_set)
    if not prompts:
        raise HTTPException(status_code=400, detail="No prompts match the selected criteria")

    # --- Create the run record ---
    run_id = str(uuid.uuid4())
    defense_json = body.defense_config.model_dump_json()
    attack_set_json = body.attack_set.model_dump_json()

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO eval_runs (id, defense_config, attack_set_config, status, total_prompts)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (run_id, defense_json, attack_set_json, len(prompts)),
        )
        await db.commit()

    # --- Register with rate limiter ---
    register_run_start(run_id, client_ip)

    # --- Set up event tracking ---
    _run_event_logs[run_id] = []
    _run_complete_events[run_id] = asyncio.Event()
    _run_queues[run_id] = asyncio.Queue()

    # --- Start the run as a background task ---
    # Store reference to prevent garbage collection (RUF006)
    task = asyncio.create_task(_run_eval_background(run_id, body.defense_config, prompts))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return EvalRunResponse(
        eval_run_id=run_id,
        status="running",
        total_prompts=len(prompts),
        stream_url=f"/api/v1/eval/run/{run_id}/stream",
    )


async def _run_eval_background(
    run_id: str,
    defense_config: Any,
    prompts: list[Any],
) -> None:
    """Background task that runs the evaluation and broadcasts events."""
    try:
        async for event in run_evaluation(run_id, defense_config, prompts):
            # Store in log (for late-joining clients)
            _run_event_logs.setdefault(run_id, []).append(event)
            # Push to queue (for active SSE clients)
            queue = _run_queues.get(run_id)
            if queue:
                await queue.put(event)
    except Exception as exc:
        logger.exception("Background run failed for %s: %s", run_id, exc)
        # Mark run as failed in DB
        async with get_db() as db:
            await db.execute(
                "UPDATE eval_runs SET status = 'failed' WHERE id = ?",
                (run_id,),
            )
            await db.commit()
        error_event = RunEvent(event="error", data={"message": str(exc)})
        _run_event_logs.setdefault(run_id, []).append(error_event)
        queue = _run_queues.get(run_id)
        if queue:
            await queue.put(error_event)
    finally:
        # Release rate limiter slot
        register_run_complete(run_id)
        # Signal completion
        complete_event = _run_complete_events.get(run_id)
        if complete_event:
            complete_event.set()
        # Send sentinel to queue
        queue = _run_queues.get(run_id)
        if queue:
            await queue.put(None)


# ---------------------------------------------------------------------------
# GET /api/v1/eval/run/{id}/stream — SSE event stream
# ---------------------------------------------------------------------------


@router.get("/run/{run_id}/stream")
async def stream_eval_run(run_id: str, request: Request) -> EventSourceResponse:
    """SSE endpoint that streams run events to the client.

    If the run is already complete, replays stored events.
    If still running, first replays stored events then streams live ones.
    """
    # Check run exists
    async with get_db() as db:
        cursor = await db.execute("SELECT id, status FROM eval_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        # Replay any already-emitted events
        past_events = _run_event_logs.get(run_id, [])
        for event in past_events:
            if await request.is_disconnected():
                return
            yield {"event": event.event, "data": event.to_sse()}

        # If the run is already complete, stop here
        complete_event = _run_complete_events.get(run_id)
        if complete_event and complete_event.is_set():
            return

        # Stream live events from the queue
        queue = _run_queues.get(run_id)
        if not queue:
            return

        # Track how many events we've already replayed to avoid duplicates
        len(past_events)
        event_index = 0

        while True:
            if await request.is_disconnected():
                return

            try:
                raw = await asyncio.wait_for(queue.get(), timeout=30.0)
            except TimeoutError:
                # Send keepalive comment
                yield {"event": "ping", "data": "keepalive"}
                continue

            if raw is None:
                # Sentinel — run finished
                return

            event_index += 1
            yield {"event": raw.event, "data": raw.to_sse()}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# GET /api/v1/eval/run/{id} — Run status and scorecard
# ---------------------------------------------------------------------------


@router.get("/run/{run_id}")
async def get_eval_run(run_id: str) -> dict[str, Any]:
    """Get the current status and scorecard of a run."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, status, defense_config, attack_set_config,
                   total_prompts, completed_prompts, summary_stats,
                   created_at
            FROM eval_runs WHERE id = ?
            """,
            (run_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")

        result: dict[str, Any] = {
            "id": row["id"],
            "status": row["status"],
            "defense_config": json.loads(row["defense_config"]),
            "attack_set_config": json.loads(row["attack_set_config"]),
            "total_prompts": row["total_prompts"],
            "completed_prompts": row["completed_prompts"],
            "created_at": row["created_at"],
        }

        if row["summary_stats"]:
            result["summary_stats"] = json.loads(row["summary_stats"])

        return result


# ---------------------------------------------------------------------------
# GET /api/v1/eval/run/{id}/results — Paginated individual results
# ---------------------------------------------------------------------------


@router.get("/run/{run_id}/results")
async def get_eval_results(
    run_id: str,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Get paginated individual results for a run."""
    async with get_db() as db:
        # Verify run exists
        cursor = await db.execute("SELECT id FROM eval_runs WHERE id = ?", (run_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Run not found")

        # Get total count
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM eval_results WHERE eval_run_id = ?",
            (run_id,),
        )
        total_row = await cursor.fetchone()
        total = total_row["cnt"] if total_row else 0

        # Fetch results page
        cursor = await db.execute(
            """
            SELECT er.*, ap.prompt_text, ap.source_dataset, ap.difficulty_estimate
            FROM eval_results er
            JOIN attack_prompts ap ON er.prompt_id = ap.id
            WHERE er.eval_run_id = ?
            ORDER BY er.created_at
            LIMIT ? OFFSET ?
            """,
            (run_id, limit, offset),
        )
        rows = await cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "prompt_id": row["prompt_id"],
                "prompt_text": row["prompt_text"][:300],
                "source_dataset": row["source_dataset"],
                "difficulty_estimate": row["difficulty_estimate"],
                "is_injection": bool(row["is_injection"]),
                "input_filter_blocked": bool(row["input_filter_blocked"]),
                "input_filter_type": row["input_filter_type"],
                "input_filter_score": row["input_filter_score"],
                "llm_response": row["llm_response"][:500] if row["llm_response"] else None,
                "llm_latency_ms": row["llm_latency_ms"],
                "output_filter_blocked": bool(row["output_filter_blocked"]),
                "output_filter_type": row["output_filter_type"],
                "injection_succeeded": row["injection_succeeded"],
                "blocked_by": row["blocked_by"],
                "semantic_eval_score": row["semantic_eval_score"],
            })

        return {
            "results": results,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
