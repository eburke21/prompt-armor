import logging
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # API keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Database
    database_path: str = "./data/promptarmor.db"

    # Rate limiting
    max_concurrent_runs: int = 3
    max_prompts_per_run: int = 200
    max_runs_per_hour: int = 10

    # Run lifecycle safety — abort a run that stalls past this deadline
    # or after this many consecutive per-prompt failures. Prevents a prolonged
    # Anthropic outage from holding a run open for hours.
    run_deadline_seconds: int = 600
    max_consecutive_prompt_failures: int = 5

    # Proxy trust — when the backend is behind Railway/Vercel/etc, request.client.host
    # is the proxy IP. Enable to read the client IP from X-Forwarded-For instead.
    # NOTE: this must NOT be enabled when the server is directly internet-facing;
    # any client could spoof their IP by setting the header themselves.
    trust_forwarded_for: bool = True

    # Server
    log_level: str = "info"
    cors_origins: str = "http://localhost:5173"

    # Boot-time ingestion — disable in production where the DB is seeded or
    # mounted from a volume; enable for local dev on a fresh checkout.
    disable_boot_ingest: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse, validate, and deduplicate CORS origins.

        Silently drops empty / malformed entries so a trailing comma or typo
        can't break CORS with `allow_credentials=True` — but logs them at
        WARN so the misconfiguration is visible.
        """
        raw = [o.strip() for o in self.cors_origins.split(",")]
        valid: list[str] = []
        seen: set[str] = set()
        for origin in raw:
            if not origin:
                continue
            parsed = urlparse(origin)
            if not parsed.scheme or not parsed.netloc:
                logger.warning("Ignoring malformed CORS origin: %r", origin)
                continue
            if origin in seen:
                continue
            seen.add(origin)
            valid.append(origin)
        return valid

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)


settings = Settings()
