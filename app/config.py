"""Central configuration (pydantic-settings). Loaded from environment / .env.

Everything defaults under <base_dir> so the system runs with zero config on a
fresh laptop; production overrides via .env (see .env.example).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCRAPER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_dir: Path = Field(default=Path(__file__).resolve().parent.parent / "data")

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    # Scoring / embeddings (M2)
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    shortlist_threshold: float = 0.6
    experience_stretch_months: int = 24

    # Gmail discovery (M1)
    gmail_credentials: Optional[Path] = None
    gmail_token: Optional[Path] = None
    gmail_query: str = (
        'newer_than:7d (from:linkedin.com OR from:naukri.com '
        'OR from:indeed.com OR subject:"job alert")'
    )

    # ---- derived paths ----
    @property
    def db_path(self) -> Path:
        return self.base_dir / "copilot.sqlite"

    @property
    def resume_dir(self) -> Path:
        return self.base_dir / "resumes"

    @property
    def backup_dir(self) -> Path:
        return self.base_dir / "backups"

    def ensure_dirs(self) -> None:
        for p in (self.base_dir, self.resume_dir, self.backup_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
