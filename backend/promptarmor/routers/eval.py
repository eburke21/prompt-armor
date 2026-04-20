"""Evaluation run API endpoints with SSE streaming.

POST /api/v1/eval/run            — start a new run
GET  /api/v1/eval/run/{id}/stream — SSE stream of results
GET  /api/v1/eval/run/{id}       — run status + scorecard
GET  /api/v1/eval/run/{id}/results — paginated individual results
POST /api/v1/eval/compare         — start a comparison (2-3 configs)
GET  /api/v1/eval/compare/{id}    — comparison status + all scorecards
GET  /api/v1/eval/compare/{id}/stream — SSE stream for comparison
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from promptarmor.config import settings
from promptarmor.database import get_db
from promptarmor.middleware.client_ip import get_client_ip
from promptarmor.middleware.rate_limit import (
    RateLimitExceeded,
    check_rate_limits,
    register_run_complete,
    register_run_start,
)
from promptarmor.models.evals import (
    ComparisonCreate,
    ComparisonResponse,
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

# Maps comparison_id → list of run_ids in the comparison
_comparison_runs: dict[str, list[str]] = {}

# Maps comparison_id → SSE queue for the comparison stream
_comparison_queues: dict[str, asyncio.Queue[RunEvent | None]] = {}

# Maps comparison_id → asyncio.Event for completion signaling
_comparison_complete_events: dict[str, asyncio.Event] = {}

# Maps comparison_id → event log (for late-joining)
_comparison_event_logs: dict[str, list[RunEvent]] = {}

# Grace period before purging in-memory SSE state after a run finishes.
# Lets late-joining / reconnecting clients replay the event log from memory.
# After expiry, the stream endpoints fall back to synthesizing terminal events
# from the DB so clients never get a silent empty stream.
_STATE_RETENTION_SECONDS = 300.0


async def _cleanup_run_state(run_id: str, delay: float = _STATE_RETENTION_SECONDS) -> None:
    """Evict in-memory SSE state for `run_id` after a grace period."""
    try:
        await asyncio.sleep(delay)
    finally:
        _run_event_logs.pop(run_id, None)
        _run_complete_events.pop(run_id, None)
        _run_queues.pop(run_id, None)


async def _cleanup_comparison_state(
    comparison_id: str,
    run_ids: list[str],
    delay: float = _STATE_RETENTION_SECONDS,
) -> None:
    """Evict comparison-level + per-run SSE state after a grace period."""
    try:
        await asyncio.sleep(delay)
    finally:
        _comparison_runs.pop(comparison_id, None)
        _comparison_queues.pop(comparison_id, None)
        _comparison_complete_events.pop(comparison_id, None)
        _comparison_event_logs.pop(comparison_id, None)
        for rid in run_ids:
            _run_event_logs.pop(rid, None)
            _run_complete_events.pop(rid, None)
            _run_queues.pop(rid, None)


def _schedule_cleanup(coro: Any) -> None:
    """Run a cleanup coroutine as a tracked background task (GC-safe)."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _synthesize_terminal_event_from_db(run_id: str) -> RunEvent | None:
    """Build a synthetic SSE event from the DB for a run whose in-memory state
    has been evicted. Returns None if the run is still in a non-terminal state
    (which would indicate the server restarted mid-run — C3 handled separately
    by the `lifespan` reconciliation that marks such rows 'failed')."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT status, summary_stats FROM eval_runs WHERE id = ?",
            (run_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    status = row["status"]
    if status in ("completed", "partial") and row["summary_stats"]:
        return RunEvent(
            event="complete",
            data={
                "scorecard": json.loads(row["summary_stats"]),
                "aborted": status == "partial",
            },
        )
    if status == "failed":
        return RunEvent(
            event="error",
            data={"message": "Run failed before completion"},
        )
    return None


# ---------------------------------------------------------------------------
# POST /api/v1/eval/run — Start a new evaluation run
# ---------------------------------------------------------------------------


@router.post("/run", status_code=201)
async def start_eval_run(body: EvalRunCreate, request: Request) -> EvalRunResponse:
    """Create a new evaluation run and kick off processing."""

    # --- Rate limiting ---
    client_ip = get_client_ip(request)
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
        # Schedule eviction of in-memory state after a grace period (C2)
        _schedule_cleanup(_cleanup_run_state(run_id))


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

        # In-memory state may have been evicted (post grace-period) or never
        # existed on this worker (post server restart). Synthesize a terminal
        # event from the DB so clients aren't left with an empty stream. (C3)
        queue = _run_queues.get(run_id)
        if queue is None:
            synthesized = await _synthesize_terminal_event_from_db(run_id)
            if synthesized is not None:
                yield {"event": synthesized.event, "data": synthesized.to_sse()}
            return

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
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
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


# ---------------------------------------------------------------------------
# POST /api/v1/eval/compare — Start a comparison eval
# ---------------------------------------------------------------------------


@router.post("/compare", status_code=201)
async def start_comparison(
    body: ComparisonCreate, request: Request
) -> ComparisonResponse:
    """Start a comparison eval: same attack set, 2-3 different defense configs."""

    # --- Rate limiting ---
    client_ip = get_client_ip(request)
    try:
        check_rate_limits(client_ip)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=exc.message,
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    # --- Validate ---
    if body.attack_set.count > settings.max_prompts_per_run:
        raise HTTPException(
            status_code=400,
            detail=f"Max {settings.max_prompts_per_run} prompts per run",
        )

    # --- Select shared attack set once ---
    prompts = await select_attacks(body.attack_set)
    if not prompts:
        raise HTTPException(
            status_code=400,
            detail="No prompts match the selected criteria",
        )

    # --- Create comparison ID and run records ---
    comparison_id = str(uuid.uuid4())
    attack_set_json = body.attack_set.model_dump_json()
    run_ids: list[str] = []

    async with get_db() as db:
        for defense_config in body.defense_configs:
            run_id = str(uuid.uuid4())
            run_ids.append(run_id)
            defense_json = defense_config.model_dump_json()
            await db.execute(
                """
                INSERT INTO eval_runs
                    (id, defense_config, attack_set_config,
                     status, total_prompts, comparison_id)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (run_id, defense_json, attack_set_json,
                 len(prompts), comparison_id),
            )
        await db.commit()

    # --- Register rate limiter for each run ---
    for run_id in run_ids:
        register_run_start(run_id, client_ip)

    # --- Set up comparison-level event tracking ---
    _comparison_runs[comparison_id] = run_ids
    _comparison_queues[comparison_id] = asyncio.Queue()
    _comparison_complete_events[comparison_id] = asyncio.Event()
    _comparison_event_logs[comparison_id] = []

    # --- Set up per-run tracking (needed for individual run endpoints) ---
    for run_id in run_ids:
        _run_event_logs[run_id] = []
        _run_complete_events[run_id] = asyncio.Event()
        _run_queues[run_id] = asyncio.Queue()

    # --- Start the comparison as a background task ---
    task = asyncio.create_task(
        _run_comparison_background(
            comparison_id, run_ids, body.defense_configs, prompts
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return ComparisonResponse(
        comparison_id=comparison_id,
        eval_run_ids=run_ids,
        total_prompts=len(prompts),
        stream_url=f"/api/v1/eval/compare/{comparison_id}/stream",
    )


async def _run_comparison_background(
    comparison_id: str,
    run_ids: list[str],
    defense_configs: list[Any],
    prompts: list[Any],
) -> None:
    """Run each defense config sequentially, broadcasting comparison events."""
    scorecards: list[dict[str, Any]] = []

    for config_index, (run_id, defense_config) in enumerate(
        zip(run_ids, defense_configs, strict=True)
    ):
        # Mark this run as running
        async with get_db() as db:
            await db.execute(
                "UPDATE eval_runs SET status = 'running' WHERE id = ?",
                (run_id,),
            )
            await db.commit()

        try:
            async for event in run_evaluation(run_id, defense_config, prompts):
                # Tag events with config_index for the comparison stream
                tagged_data = {**event.data, "config_index": config_index}
                tagged_event = RunEvent(event=event.event, data=tagged_data)

                # Push to per-run tracking
                _run_event_logs.setdefault(run_id, []).append(event)
                run_queue = _run_queues.get(run_id)
                if run_queue:
                    await run_queue.put(event)

                # Push to comparison stream
                _comparison_event_logs.setdefault(
                    comparison_id, []
                ).append(tagged_event)
                comp_queue = _comparison_queues.get(comparison_id)
                if comp_queue:
                    await comp_queue.put(tagged_event)

                # If this is the complete event, capture the scorecard
                if event.event == "complete":
                    scorecards.append(event.data.get("scorecard", {}))

        except Exception as exc:
            logger.exception(
                "Comparison run %s (config %d) failed: %s",
                run_id, config_index, exc,
            )
            async with get_db() as db:
                await db.execute(
                    "UPDATE eval_runs SET status = 'failed' WHERE id = ?",
                    (run_id,),
                )
                await db.commit()

            error_event = RunEvent(
                event="error",
                data={
                    "message": str(exc),
                    "config_index": config_index,
                },
            )
            _comparison_event_logs.setdefault(
                comparison_id, []
            ).append(error_event)
            comp_queue = _comparison_queues.get(comparison_id)
            if comp_queue:
                await comp_queue.put(error_event)
        finally:
            # Release per-run resources
            register_run_complete(run_id)
            run_complete = _run_complete_events.get(run_id)
            if run_complete:
                run_complete.set()
            run_queue = _run_queues.get(run_id)
            if run_queue:
                await run_queue.put(None)

        # Emit config_complete event for the comparison stream
        config_complete_event = RunEvent(
            event="config_complete",
            data={
                "config_index": config_index,
                "eval_run_id": run_id,
                "scorecard": scorecards[-1] if scorecards else {},
            },
        )
        _comparison_event_logs.setdefault(
            comparison_id, []
        ).append(config_complete_event)
        comp_queue = _comparison_queues.get(comparison_id)
        if comp_queue:
            await comp_queue.put(config_complete_event)

    # All configs done — emit all_complete
    all_complete_event = RunEvent(
        event="all_complete",
        data={
            "comparison_id": comparison_id,
            "scorecards": scorecards,
        },
    )
    _comparison_event_logs.setdefault(
        comparison_id, []
    ).append(all_complete_event)
    comp_queue = _comparison_queues.get(comparison_id)
    if comp_queue:
        await comp_queue.put(all_complete_event)
        await comp_queue.put(None)  # Sentinel

    comp_complete = _comparison_complete_events.get(comparison_id)
    if comp_complete:
        comp_complete.set()

    # Schedule eviction of in-memory comparison + per-run state (C2)
    _schedule_cleanup(_cleanup_comparison_state(comparison_id, run_ids))


# ---------------------------------------------------------------------------
# GET /api/v1/eval/compare/{id}/stream — Comparison SSE stream
# ---------------------------------------------------------------------------


@router.get("/compare/{comparison_id}/stream")
async def stream_comparison(
    comparison_id: str, request: Request
) -> EventSourceResponse:
    """SSE stream for a comparison eval, interleaving results from all configs."""
    # Verify the comparison exists in the DB (in-memory state may have been
    # evicted post-completion, so we can't rely on _comparison_runs for 404).
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM eval_runs WHERE comparison_id = ?",
            (comparison_id,),
        )
        row = await cursor.fetchone()
    if not row or row["cnt"] == 0:
        raise HTTPException(status_code=404, detail="Comparison not found")

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        # Replay past events
        past = _comparison_event_logs.get(comparison_id, [])
        for event in past:
            if await request.is_disconnected():
                return
            yield {"event": event.event, "data": event.to_sse()}

        # If already complete, stop
        comp_complete = _comparison_complete_events.get(comparison_id)
        if comp_complete and comp_complete.is_set():
            return

        # In-memory state evicted or never existed — synthesize an all_complete
        # event from the DB if all runs in the comparison are terminal. (C3)
        queue = _comparison_queues.get(comparison_id)
        if queue is None:
            async with get_db() as db:
                cur = await db.execute(
                    """
                    SELECT id, status, summary_stats
                    FROM eval_runs WHERE comparison_id = ?
                    ORDER BY created_at
                    """,
                    (comparison_id,),
                )
                rows = await cur.fetchall()
            scorecards = [
                json.loads(r["summary_stats"]) if r["summary_stats"] else {}
                for r in rows
            ]
            yield {
                "event": "all_complete",
                "data": json.dumps({
                    "comparison_id": comparison_id,
                    "scorecards": scorecards,
                }),
            }
            return

        while True:
            if await request.is_disconnected():
                return
            try:
                raw = await asyncio.wait_for(queue.get(), timeout=30.0)
            except TimeoutError:
                yield {"event": "ping", "data": "keepalive"}
                continue

            if raw is None:
                return
            yield {"event": raw.event, "data": raw.to_sse()}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# GET /api/v1/eval/compare/{id} — Comparison status + all scorecards
# ---------------------------------------------------------------------------


@router.get("/compare/{comparison_id}")
async def get_comparison(comparison_id: str) -> dict[str, Any]:
    """Get all runs in a comparison with their scorecards."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, status, defense_config, attack_set_config,
                   total_prompts, completed_prompts, summary_stats,
                   created_at
            FROM eval_runs
            WHERE comparison_id = ?
            ORDER BY created_at
            """,
            (comparison_id,),
        )
        rows = await cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Comparison not found")

    runs: list[dict[str, Any]] = []
    all_complete = True

    for idx, row in enumerate(rows):
        run_data: dict[str, Any] = {
            "config_index": idx,
            "id": row["id"],
            "status": row["status"],
            "defense_config": json.loads(row["defense_config"]),
            "total_prompts": row["total_prompts"],
            "completed_prompts": row["completed_prompts"],
        }
        if row["summary_stats"]:
            run_data["summary_stats"] = json.loads(row["summary_stats"])
        else:
            all_complete = False
        if row["status"] not in ("completed", "partial"):
            all_complete = False
        runs.append(run_data)

    return {
        "comparison_id": comparison_id,
        "status": "completed" if all_complete else "running",
        "runs": runs,
    }
