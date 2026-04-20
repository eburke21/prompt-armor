"""In-memory rate limiting for evaluation runs.

Tracks:
- Concurrent active runs (max 3 globally)
- Runs per hour per IP (max 10, sliding window)

These limits protect against runaway Claude API costs on a public demo.

Implementation note: state lives on a `RateLimiter` instance rather than
module globals so tests can construct isolated instances and so a future
Redis-backed variant can be swapped in without touching callers.
"""

import logging
import time
from collections import defaultdict

from promptarmor.config import settings

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 3600  # 1 hour


class RateLimitExceeded(Exception):
    """Raised when a rate limit is hit."""

    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class RateLimiter:
    """In-memory rate limiter with per-IP and global concurrency limits."""

    def __init__(self, window_seconds: int = _WINDOW_SECONDS) -> None:
        self._window_seconds = window_seconds
        self._active_run_ids: set[str] = set()
        self._runs_by_ip: dict[str, list[float]] = defaultdict(list)

    def check(self, client_ip: str) -> None:
        """Raise RateLimitExceeded if any limit would be exceeded."""
        if len(self._active_run_ids) >= settings.max_concurrent_runs:
            raise RateLimitExceeded(
                f"Maximum {settings.max_concurrent_runs} concurrent runs — "
                "please wait for a running evaluation to complete",
                retry_after=30,
            )

        now = time.time()
        self._prune_old_entries(client_ip, now)

        recent_count = len(self._runs_by_ip[client_ip])
        if recent_count >= settings.max_runs_per_hour:
            oldest = self._runs_by_ip[client_ip][0]
            retry_after = int(oldest + self._window_seconds - now) + 1
            raise RateLimitExceeded(
                f"Maximum {settings.max_runs_per_hour} runs per hour — "
                f"try again in {retry_after} seconds",
                retry_after=retry_after,
            )

    def register_start(self, run_id: str, client_ip: str) -> None:
        """Record that a new run has started."""
        self._active_run_ids.add(run_id)
        self._runs_by_ip[client_ip].append(time.time())
        logger.info(
            "Run %s started (active: %d, IP %s hourly: %d)",
            run_id,
            len(self._active_run_ids),
            client_ip,
            len(self._runs_by_ip[client_ip]),
        )

    def register_complete(self, run_id: str) -> None:
        """Record that a run has finished (success or failure)."""
        self._active_run_ids.discard(run_id)
        logger.info("Run %s completed (active: %d)", run_id, len(self._active_run_ids))

    def active_count(self) -> int:
        return len(self._active_run_ids)

    def reset(self) -> None:
        """Clear all state. Intended for tests."""
        self._active_run_ids.clear()
        self._runs_by_ip.clear()

    def _prune_old_entries(self, client_ip: str, now: float) -> None:
        cutoff = now - self._window_seconds
        self._runs_by_ip[client_ip] = [
            t for t in self._runs_by_ip[client_ip] if t > cutoff
        ]


# Module-level singleton — the request handlers call these functions.
# Tests that want isolation should instantiate their own RateLimiter.
_default_limiter = RateLimiter()


def check_rate_limits(client_ip: str) -> None:
    _default_limiter.check(client_ip)


def register_run_start(run_id: str, client_ip: str) -> None:
    _default_limiter.register_start(run_id, client_ip)


def register_run_complete(run_id: str) -> None:
    _default_limiter.register_complete(run_id)


def get_active_run_count() -> int:
    return _default_limiter.active_count()


def _reset_default_limiter() -> None:
    """Reset the module singleton. Intended for tests."""
    _default_limiter.reset()
