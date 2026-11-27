"""Application settings.

Every tunable constant (thresholds, depths, timeouts) lives here. Values in `Settings` can be
overridden through environment variables or the repo-root `.env` file.
"""

import os
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_pool_size() -> int:
    """CPU count - 1, between 1 and 4 (a Raspberry Pi 4 has 4 cores)."""
    return max(1, min(4, (os.cpu_count() or 2) - 1))


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
    # Scale of the minimum "thinking" time shown before the bot's reply (LevelPreset.think_*):
    # 0 turns it off (tests).
    bot_think_scale: float = 1.0
    # Full-strength search time used to compute a hint.
    hint_time_s: float = 0.3
    # Search time used to evaluate a draw offer.
    draw_eval_time_s: float = 0.3
    # The bot accepts a draw if its evaluation (its own point of view) is <= this, in centipawns.
    draw_accept_max_cp: int = 30
    # ...and never before this many full moves have been played in this game (a game started
    # from a FEN counts only the moves played since that position).
    draw_min_moves: int = 20
    # Name of the human player in PGN headers.
    player_name: str = "Jugador"

    # --- Analysis ---------------------------------------------------------
    # Engines analysing positions in parallel (separate from the play engine).
    engine_pool_size: int = Field(default_factory=_default_pool_size)
    # Per-position search: time limit, optional depth limit (whichever comes first).
    analysis_time_s: float = 0.5
    analysis_depth: int | None = None
    analysis_multipv: int = 3
    analysis_threads: int = 1
    analysis_hash_mb: int = 32
    # Close the analysis engines after this many idle seconds (frees memory on a Pi).
    analysis_pool_idle_s: float = 120.0
    # On-demand evaluation (exploring variations, coach tool): search time and line length.
    evaluate_time_s: float = 0.3
    evaluate_max_multipv: int = 5
    evaluate_line_plies: int = 6
    # "Ver por qué" (Phase 5): search time of each extension of a line that is too short to
    # reach its consequence point (one engine line, cached per position), and how long each
    # step of the replay lasts in the browser.
    why_extend_time_s: float = 0.2
    # Online sync (phase 6a): public APIs (overridable for tests), a generic User-Agent (no
    # personal data), how far back the first sync (and each "older games" step) goes, timeouts
    # and the wait before retrying after HTTP 429.
    lichess_url: str = "https://lichess.org"
    chesscom_url: str = "https://api.chess.com"
    sync_user_agent: str = "whyfish (local chess learning app)"
    sync_months: int = 6
    sync_timeout_s: float = 30.0
    sync_retry_wait_s: float = 60.0
    # Background analysis queue: engines left free for interactive use, optional rest between
    # games (e.g. to let a Raspberry Pi cool down), and whether it runs at all.
    queue_reserved_engines: int = 1
    queue_pause_between_s: float = 0.0
    queue_enabled: bool = True
    # Statistics data is computed in a separate process (not to compete with the server for
    # the GIL); False runs it in a thread (unit tests).
    insights_process: bool = True
    why_step_ms: int = 1000

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
    # Minimum "thinking" time shown before the bot's reply (SPEC §1.1), random in this range
    # (seconds). Applied by the frontend: it only waits for what the request did not take.
    think_min_s: float = 0.5
    think_max_s: float = 0.5


LEVEL_PRESETS: dict[BotLevel, LevelPreset] = {
    BotLevel.BEGINNER: LevelPreset(
        "Principiante ~800", skill_level=0, depth=1, think_min_s=0.8, think_max_s=1.6
    ),
    BotLevel.NOVICE: LevelPreset(
        "Novato ~1100", skill_level=3, depth=4, think_min_s=0.8, think_max_s=1.6
    ),
    BotLevel.CLUB: LevelPreset("Club ~1500", uci_elo=1500, think_min_s=0.8, think_max_s=1.8),
    BotLevel.STRONG: LevelPreset("Fuerte ~2000", uci_elo=2000),
    BotLevel.MAX: LevelPreset("Máximo"),
}


# --- Move classification (SPEC §3) -------------------------------------------
# All values are win-percentage points (0-100) from the mover's point of view.


@dataclass(frozen=True)
class ClassificationThresholds:
    # Δ upper bounds (exclusive) for the plain categories; Δ >= mistake -> blunder.
    excellent: float = 2.0
    good: float = 5.0
    inaccuracy: float = 10.0
    mistake: float = 20.0
    # Moves "as good as the best" (SPEC §3): Δ below this win%. Such a move is also ★, and the
    # coach names the other equal moves ("También valía [[Y]]").
    equal_max_delta: float = 1.0
    # Decided positions (mover's win% above `decided_above` or below 100 - it): win% saturates,
    # so moves are compared by score (centipawns; mate = MATE_SCORE - 10 per move). Equal when
    # within `decided_equal_max_cp`; at most excellent up to `decided_excellent_max_cp`, at
    # most good beyond (winning a pawn instead of a rook is not ★ just because both "win").
    decided_above: float = 85.0
    decided_equal_max_cp: int = 50
    decided_excellent_max_cp: int = 150
    # A book move only counts as theory if it is not an error (Δ below this); the opening
    # dataset also contains traps such as "Barnes Opening: Fool's Mate".
    book_max_delta: float = 10.0
    # Great move (!): the second MultiPV option is at least this much worse...
    great_min_gap: float = 10.0
    # ...or falls into another outcome category (winning > winning_above, losing < losing_below).
    winning_above: float = 75.0
    losing_below: float = 25.0
    # Never great when the position was already this good (keeping a won game is not notable).
    great_max_win_before: float = 85.0
    # Brilliant (!!).
    brilliant_max_delta: float = 2.0
    brilliant_max_win_before: float = 90.0  # exclusive: not already totally winning
    brilliant_min_win_after: float = 45.0
    # No brilliant when the mover was already down material (resolved) before the move: it is
    # the continuation of an own combination, not a new sacrifice.
    brilliant_min_material_before: int = 0
    sacrifice_min_material: int = 2  # points (P=1, N=B=3, R=5, Q=9)
    sacrifice_horizon_plies: int = 6
    # Quiescence depth (captures, promotions and check evasions) used to resolve pending
    # exchanges when measuring material for sacrifices.
    quiescence_max_plies: int = 8
    # Missed opportunity: after an opponent's ? / ??, Δ >= this and the best move reached
    # at least `missed_decisive_win`.
    missed_min_delta: float = 10.0
    missed_decisive_win: float = 80.0
    # Key moments (SPEC §3.4).
    key_moments_max: int = 5
    key_moment_min_delta: float = 5.0


THRESHOLDS = ClassificationThresholds()


# --- Facts and explanations (SPEC §4-5) ----------------------------------------


@dataclass(frozen=True)
class FactThresholds:
    # Smallest material swing (P=1, N=B=3, R=5, Q=9) the explanations talk about.
    material_min: int = 1
    # Motifs (fork, pin, ...) are looked for in the first plies of a line only.
    motif_plies: int = 4
    # "Wins material" is only said if the line shows a capture of ours and the mover's win% in
    # that line is at least this (otherwise the "gain" is an opponent's sacrifice in progress).
    gain_claim_min_win: float = 55.0
    # Phase: opening up to this full move; endgame when the non-pawn material of both sides
    # together (kings excluded) is at most this many points.
    opening_max_fullmove: int = 10
    endgame_max_material: int = 16
    # "Mate in N" is spelled out (with its moves) up to this N; beyond that, "un ataque de mate".
    mate_spell_max: int = 3
    # Annotations drawn on the board: level 1 (main idea only) and level 2.
    annotations_level1_max: int = 3
    annotations_level2_max: int = 6
    # Plies of a commented line in level 2.
    commented_line_plies: int = 6
    # Consequence point (SPEC §5.3): lines are followed at most this many plies, and the
    # quiescence that decides whether a position is quiet goes this deep.
    consequence_max_plies: int = 20
    quiescence_max_plies: int = 8
    # A gain or loss is stated in the level-1 text only if its consequence point is within
    # this many plies of the line: the same limit as "Ver por qué", which replays up to it.
    consequence_text_max_plies: int = 20
    # "Ver por qué": plies without material change required after the consequence point (not
    # for mate), and plies replayed when there is no clear consequence.
    why_stable_plies: int = 4
    why_quiet_plies: int = 8


FACTS = FactThresholds()


# --- Statistics (phase 6b) -------------------------------------------------------------------


@dataclass(frozen=True)
class StatsThresholds:
    # Fewer analysed games than this: the page warns that conclusions are shaky.
    min_games: int = 10
    # An opening (family, colour) is judged with at least this many games.
    opening_min_games: int = 3
    # Low time: remaining clock below the smaller of these (seconds / fraction of the base time).
    low_time_s: float = 30.0
    low_time_fraction: float = 0.10
    # "Gestión del tiempo" is a weak point when errors are this many times more frequent with
    # low time than without, over at least `time_min_moves` low-time moves.
    time_weak_ratio: float = 2.0
    time_min_moves: int = 20
    # A weak point (error type x phase) needs at least this many errors.
    weak_min_errors: int = 3
    weak_points: int = 3
    examples_max: int = 20
    moving_average: int = 5


STATS = StatsThresholds()


# --- Training (phase 6c) ---------------------------------------------------------------------


@dataclass(frozen=True)
class TrainingThresholds:
    session_size: int = 5  # exercises of the daily session (changeable in Ajustes)
    # Of the new exercises of a daily session, up to this many from the error kinds of the
    # weak points ("Tus 3 puntos débiles"); the rest, the most recent errors.
    weak_new: int = 3
    # Leitner boxes 1-5: days until the exercise comes back; right in box 5 = learned.
    intervals: tuple[int, ...] = (1, 2, 4, 8, 16)
    # Not exercises: decided positions (win% before above / below 100 - this) and positions
    # where the best move has this many equally good alternatives or more.
    decided_above: float = 85.0
    unclear_alternatives: int = 2
    include_bullet: bool = False  # errors of bullet games (changeable in Ajustes)
    # Errors of games against the bot: only when no real game's exercise is left (Ajustes).
    include_bot: bool = True


TRAINING = TrainingThresholds()


# --- Interface (phase 6.5) -------------------------------------------------------------------


@dataclass(frozen=True)
class UiDefaults:
    """Defaults of the interface settings (changeable in Ajustes, stored in the database)."""

    color_mode: str = "system"  # system | light | dark
    board: str = "brown"  # brown | blue | gray | wood | slate
    pieces: str = "cburnett"  # cburnett | mpchess | chessnut | rhosgfx


UI = UiDefaults()
