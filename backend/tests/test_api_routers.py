"""End-to-end tests for the FastAPI router layer.

These tests exercise the HTTP surface (status codes, response shapes,
validation errors, rate limiting) that unit tests on services can't reach.
They catch regressions like the "taxonomy endpoint crashes on empty DB" bug
that motivated the I13 review item.
"""

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Taxonomy on an empty database
# ---------------------------------------------------------------------------


class TestTaxonomyEndpoint:
    async def test_taxonomy_returns_zeros_on_empty_db(
        self, api_client: AsyncClient
    ) -> None:
        """Regression test: before the `COALESCE`/empty-check fix, an empty
        DB returned 500 — now it must return 200 with zero counts."""
        res = await api_client.get("/api/v1/taxonomy")
        assert res.status_code == 200
        body = res.json()
        assert body["total_prompts"] == 0
        assert body["total_injections"] == 0
        assert body["total_benign"] == 0
        assert body["techniques"] == []
        assert body["datasets"] == []


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    async def test_health_returns_ok(self, api_client: AsyncClient) -> None:
        res = await api_client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "database": "connected"}


# ---------------------------------------------------------------------------
# Eval run creation — validation + rate limiting
# ---------------------------------------------------------------------------


def _valid_eval_body(count: int = 20) -> dict:
    return {
        "defense_config": {
            "system_prompt": "You are a helpful assistant.",
            "input_filters": [],
            "output_filters": [],
        },
        "attack_set": {
            "techniques": ["goal_hijack"],
            "difficulty_range": [1, 5],
            "count": count,
            "include_benign": False,
            "benign_ratio": 0.0,
        },
    }


class TestEvalRunValidation:
    async def test_rejects_malformed_body(self, api_client: AsyncClient) -> None:
        res = await api_client.post("/api/v1/eval/run", json={"not": "valid"})
        assert res.status_code == 422

    async def test_rejects_count_above_pydantic_limit(
        self, api_client: AsyncClient
    ) -> None:
        """AttackSetConfig.count has ge=1, le=200 at the Pydantic layer."""
        body = _valid_eval_body(count=500)
        res = await api_client.post("/api/v1/eval/run", json=body)
        assert res.status_code == 422

    async def test_rejects_no_matching_prompts(
        self, api_client: AsyncClient
    ) -> None:
        """With an empty DB, no prompts match — endpoint must return 400,
        never proceed to create a run row."""
        res = await api_client.post("/api/v1/eval/run", json=_valid_eval_body())
        assert res.status_code == 400
        assert "no prompts" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /eval/run/{id}/results — pagination bounds
# ---------------------------------------------------------------------------


class TestResultsPagination:
    async def test_results_rejects_huge_limit(self, api_client: AsyncClient) -> None:
        """Unbounded limit was a DoS vector (C6). Query(le=200) now enforces it."""
        res = await api_client.get(
            "/api/v1/eval/run/any-id/results", params={"limit": 10_000}
        )
        assert res.status_code == 422

    async def test_results_rejects_negative_offset(
        self, api_client: AsyncClient
    ) -> None:
        res = await api_client.get(
            "/api/v1/eval/run/any-id/results", params={"offset": -1}
        )
        assert res.status_code == 422

    async def test_results_404_for_missing_run(
        self, api_client: AsyncClient
    ) -> None:
        res = await api_client.get(
            "/api/v1/eval/run/does-not-exist/results",
            params={"limit": 10, "offset": 0},
        )
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Run metadata 404
# ---------------------------------------------------------------------------


class TestRunMetadata:
    async def test_get_run_404(self, api_client: AsyncClient) -> None:
        res = await api_client.get("/api/v1/eval/run/does-not-exist")
        assert res.status_code == 404

    async def test_stream_404(self, api_client: AsyncClient) -> None:
        res = await api_client.get("/api/v1/eval/run/does-not-exist/stream")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Rate limit returns 429 with Retry-After header
# ---------------------------------------------------------------------------


class TestRateLimitResponse:
    async def test_concurrent_cap_returns_429_with_retry_after(
        self, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Seed the singleton at its concurrent cap so any incoming request
        trips the limiter. The handler must respond 429 + Retry-After."""
        from promptarmor.middleware import rate_limit as rl

        for i in range(rl.settings.max_concurrent_runs):
            rl.register_run_start(f"seed-{i}", "1.2.3.4")

        res = await api_client.post("/api/v1/eval/run", json=_valid_eval_body())
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert int(res.headers["Retry-After"]) > 0
