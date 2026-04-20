"""Tests for the in-memory rate limiter.

Two styles exercised:
- Instance-level (preferred): construct a fresh RateLimiter per test.
- Module-singleton: exercise the public functions that the route handlers use.
  Isolated with a pytest fixture that resets the singleton before each test.
"""

import pytest

from promptarmor.middleware import rate_limit
from promptarmor.middleware.rate_limit import (
    RateLimiter,
    RateLimitExceeded,
    check_rate_limits,
    register_run_complete,
    register_run_start,
)


@pytest.fixture(autouse=True)
def _reset_singleton_state() -> None:
    """Clear rate limiter singleton state before each test (xdist-safe)."""
    rate_limit._reset_default_limiter()


class TestRateLimiter:
    def test_allows_first_run(self) -> None:
        check_rate_limits("127.0.0.1")

    def test_blocks_concurrent_over_limit(self) -> None:
        register_run_start("run-1", "127.0.0.1")
        register_run_start("run-2", "127.0.0.1")
        register_run_start("run-3", "127.0.0.1")

        with pytest.raises(RateLimitExceeded, match="concurrent"):
            check_rate_limits("127.0.0.1")

    def test_allows_after_run_completes(self) -> None:
        register_run_start("run-1", "127.0.0.1")
        register_run_start("run-2", "127.0.0.1")
        register_run_start("run-3", "127.0.0.1")
        register_run_complete("run-1")

        check_rate_limits("127.0.0.1")

    def test_blocks_per_ip_hourly_limit(self) -> None:
        for i in range(10):
            register_run_start(f"run-{i}", "10.0.0.1")
            register_run_complete(f"run-{i}")

        with pytest.raises(RateLimitExceeded, match="per hour"):
            check_rate_limits("10.0.0.1")

    def test_different_ips_independent(self) -> None:
        for i in range(10):
            register_run_start(f"run-a-{i}", "10.0.0.1")
            register_run_complete(f"run-a-{i}")

        check_rate_limits("10.0.0.2")

    def test_register_and_complete_tracking(self) -> None:
        register_run_start("run-x", "127.0.0.1")
        assert rate_limit.get_active_run_count() == 1
        register_run_complete("run-x")
        assert rate_limit.get_active_run_count() == 0

    def test_complete_nonexistent_run_is_safe(self) -> None:
        register_run_complete("nonexistent")


class TestRateLimiterInstance:
    """Same behavior, verified via an isolated instance (no shared state)."""

    def test_concurrent_limit_enforced_per_instance(self) -> None:
        limiter = RateLimiter()
        limiter.register_start("r1", "1.1.1.1")
        limiter.register_start("r2", "1.1.1.1")
        limiter.register_start("r3", "1.1.1.1")
        with pytest.raises(RateLimitExceeded, match="concurrent"):
            limiter.check("1.1.1.1")

    def test_two_instances_are_isolated(self) -> None:
        a = RateLimiter()
        b = RateLimiter()
        a.register_start("r1", "1.1.1.1")
        a.register_start("r2", "1.1.1.1")
        a.register_start("r3", "1.1.1.1")
        # A is saturated; B should still allow runs.
        b.check("1.1.1.1")
