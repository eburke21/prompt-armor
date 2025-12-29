from pathlib import Path

from pydantic_settings import BaseSettings


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

    # Server
    log_level: str = "info"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)


settings = Settings()
