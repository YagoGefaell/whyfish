from datetime import datetime
from typing import Literal

import chess
from pydantic import BaseModel

from app.config import LEVEL_PRESETS, BotLevel
from app.models.game import Game
from app.play.rules import DrawDecline, PlayerColor, Termination
from app.play.service import ColorChoice, LoadedGame


class LevelRead(BaseModel):
    id: BotLevel
    label: str


class GameCreate(BaseModel):
    color: ColorChoice = ColorChoice.WHITE
    level: BotLevel = BotLevel.CLUB
    allow_undo: bool = False
    allow_hint: bool = False
    # Optional start position; blank means the standard start.
    fen: str | None = None


class MoveCreate(BaseModel):
    uci: str


class MoveRead(BaseModel):
    ply: int
    uci: str
    san: str
    by_bot: bool


class GameSummary(BaseModel):
    id: int
    created_at: datetime
    player_color: PlayerColor
    bot_level: BotLevel
    bot_level_label: str
    result: str | None
    termination: Termination | None
    move_count: int

    @classmethod
    def from_game(cls, game: Game, move_count: int) -> "GameSummary":
        assert game.id is not None
        return cls(
            id=game.id,
            created_at=game.created_at,
            player_color=game.player_color,
            bot_level=game.bot_level,
            bot_level_label=LEVEL_PRESETS[game.bot_level].label,
            result=game.result,
            termination=game.termination,
            move_count=move_count,
        )


class GameState(GameSummary):
    status: Literal["ongoing", "finished"]
    initial_fen: str
    fen: str
    turn: PlayerColor
    moves: list[MoveRead]
    allow_undo: bool
    allow_hint: bool
    undo_count: int
    hint_count: int

    @classmethod
    def from_loaded(cls, loaded: LoadedGame) -> "GameState":
        game = loaded.game
        summary = GameSummary.from_game(game, len(loaded.moves))
        return cls(
            **summary.model_dump(),
            status="finished" if game.is_over else "ongoing",
            initial_fen=game.initial_fen,
            fen=loaded.board.fen(),
            turn=PlayerColor.WHITE if loaded.board.turn == chess.WHITE else PlayerColor.BLACK,
            moves=[
                MoveRead(ply=m.ply, uci=m.uci, san=m.san, by_bot=m.by_bot) for m in loaded.moves
            ],
            allow_undo=game.allow_undo,
            allow_hint=game.allow_hint,
            undo_count=game.undo_count,
            hint_count=game.hint_count,
        )


class HintRead(BaseModel):
    square: str  # Square of the piece to move, e.g. "g1"


class DrawOfferRead(BaseModel):
    accepted: bool
    # Why the bot declined: "too_early" (fewer than `min_moves` played) or "position" (evaluation).
    declined_reason: DrawDecline | None
    min_moves: int
    game: GameState
