"""Application settings.

Every tunable constant (thresholds, depths, timeouts) lives here. Values can be
overridden through environment variables or the repo-root `.env` file.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Engine -----------------------------------------------------------
    stockfish_path: Path | None = None
    engine_threads: int = 1
    engine_hash_mb: int = 64
    # Max seconds to wait for the engine to start and complete the UCI handshake.
    engine_start_timeout_s: float = 10.0
    # Max seconds to wait for `isready` during a healthcheck.
    engine_ping_timeout_s: float = 2.0
    # Max seconds to wait for a clean `quit` before killing the process.
    engine_quit_timeout_s: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
