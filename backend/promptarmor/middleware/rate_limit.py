"""In-memory rate limiting for evaluation runs.

Tracks:
- Concurrent active runs (max 3 globally)
- Runs per hour per IP (max 10, sliding window)

These limits protect against runaway Claude API costs on a public demo.
"""

import logging
import time
from collections import defaultdict

from promptarmor.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State — all in-memory, resets on server restart
# ---------------------------------------------------------------------------

_active_run_ids: set[str] = set()
_runs_by_ip: dict[str, list[float]] = defaultdict(list)  # IP → list of start timestamps

_WINDOW_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class RateLimitExceeded(Exception):
    """Raised when a rate limit is hit."""

    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


def check_rate_limits(client_ip: str) -> None:
    """Check all rate limits before starting a new run.

    Raises RateLimitExceeded if any limit is hit.
    """
    # --- Concurrent runs limit ---
    if len(_active_run_ids) >= settings.max_concurrent_runs:
        raise RateLimitExceeded(
            f"Maximum {settings.max_concurrent_runs} concurrent runs — "
            "please wait for a running evaluation to complete",
            retry_after=30,
        )

    # --- Per-IP hourly limit ---
    now = time.time()
    _prune_old_entries(client_ip, now)

    recent_count = len(_runs_by_ip[client_ip])
    if recent_count >= settings.max_runs_per_hour:
        # Calculate when the oldest entry will expire
        oldest = _runs_by_ip[client_ip][0]
        retry_after = int(oldest + _WINDOW_SECONDS - now) + 1
        raise RateLimitExceeded(
            f"Maximum {settings.max_runs_per_hour} runs per hour — "
            f"try again in {retry_after} seconds",
            retry_after=retry_after,
        )


def register_run_start(run_id: str, client_ip: str) -> None:
    """Record that a new run has started."""
    _active_run_ids.add(run_id)
    _runs_by_ip[client_ip].append(time.time())
    logger.info(
        "Run %s started (active: %d, IP %s hourly: %d)",
        run_id,
        len(_active_run_ids),
        client_ip,
        len(_runs_by_ip[client_ip]),
    )


def register_run_complete(run_id: str) -> None:
    """Record that a run has finished (success or failure)."""
    _active_run_ids.discard(run_id)
    logger.info("Run %s completed (active: %d)", run_id, len(_active_run_ids))


def get_active_run_count() -> int:
    """Return the number of currently active runs."""
    return len(_active_run_ids)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _prune_old_entries(client_ip: str, now: float) -> None:
    """Remove timestamps older than the sliding window."""
    cutoff = now - _WINDOW_SECONDS
    _runs_by_ip[client_ip] = [t for t in _runs_by_ip[client_ip] if t > cutoff]
