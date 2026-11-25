"""Application settings.

Every tunable constant (thresholds, depths, timeouts) lives here. Values in `Settings` can be
overridden through environment variables or the repo-root `.env` file.
"""

from dataclasses import dataclass
from enum import StrEnum
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

    # --- Play -------------------------------------------------------------
    # Upper bound on the bot's thinking time per move, for every level.
    bot_movetime_s: float = 1.0
    # Full-strength search time used to compute a hint.
    hint_time_s: float = 0.3
    # Search time used to evaluate a draw offer.
    draw_eval_time_s: float = 0.3
    # The bot accepts a draw if its evaluation (its own point of view) is <= this, in centipawns.
    draw_accept_max_cp: int = 30
    # Name of the human player in PGN headers.
    player_name: str = "Jugador"

    # --- Storage ----------------------------------------------------------
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'whyfish.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --- Bot levels -------------------------------------------------------------


class BotLevel(StrEnum):
    BEGINNER = "beginner"
    NOVICE = "novice"
    CLUB = "club"
    STRONG = "strong"
    MAX = "max"


@dataclass(frozen=True)
class LevelPreset:
    """How a bot level is obtained from Stockfish.

    Stockfish 19 only supports `UCI_Elo` in [1320, 3190]. Levels below that use
    `Skill Level` plus a depth cap; their Elo labels are rough and uncalibrated.
    The search is always capped by `Settings.bot_movetime_s` as well.
    """

    label: str
    skill_level: int | None = None
    uci_elo: int | None = None
    depth: int | None = None


LEVEL_PRESETS: dict[BotLevel, LevelPreset] = {
    BotLevel.BEGINNER: LevelPreset("Principiante ~800", skill_level=0, depth=1),
    BotLevel.NOVICE: LevelPreset("Novato ~1100", skill_level=3, depth=4),
    BotLevel.CLUB: LevelPreset("Club ~1500", uci_elo=1500),
    BotLevel.STRONG: LevelPreset("Fuerte ~2000", uci_elo=2000),
    BotLevel.MAX: LevelPreset("Máximo"),
}
