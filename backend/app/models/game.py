from datetime import UTC, datetime

import chess
from sqlmodel import Field, SQLModel

from app.config import BotLevel
from app.play.rules import PlayerColor, Termination


def utcnow() -> datetime:
    return datetime.now(UTC)


class Game(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None
    player_color: PlayerColor
    bot_level: BotLevel
    initial_fen: str = chess.STARTING_FEN
    allow_undo: bool = False
    allow_hint: bool = False
    undo_count: int = 0
    hint_count: int = 0
    # "1-0", "0-1", "1/2-1/2"; None while the game is ongoing.
    result: str | None = None
    termination: Termination | None = None

    @property
    def is_over(self) -> bool:
        return self.result is not None


class Move(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)
    ply: int  # 0-based
    uci: str
    san: str
    fen_after: str
    by_bot: bool
