"""Tests for the in-memory rate limiter."""

import pytest

from promptarmor.middleware.rate_limit import (
    RateLimitExceeded,
    _active_run_ids,
    _runs_by_ip,
    check_rate_limits,
    register_run_complete,
    register_run_start,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Clear rate limiter state before each test."""
    _active_run_ids.clear()
    _runs_by_ip.clear()


class TestRateLimiter:
    def test_allows_first_run(self) -> None:
        check_rate_limits("127.0.0.1")  # Should not raise

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

        check_rate_limits("127.0.0.1")  # Should not raise

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

        # Different IP should be fine
        check_rate_limits("10.0.0.2")  # Should not raise

    def test_register_and_complete_tracking(self) -> None:
        register_run_start("run-x", "127.0.0.1")
        assert "run-x" in _active_run_ids
        register_run_complete("run-x")
        assert "run-x" not in _active_run_ids

    def test_complete_nonexistent_run_is_safe(self) -> None:
        register_run_complete("nonexistent")  # Should not raise
