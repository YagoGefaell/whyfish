"""Pure chess/game rules for playing against the bot. No I/O, no engine calls."""

import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

import chess
import chess.engine
import chess.pgn

from app.config import LevelPreset

# Mate scores are mapped to this many centipawns when comparing evaluations.
MATE_SCORE_CP = 100_000


class PlayerColor(StrEnum):
    WHITE = "white"
    BLACK = "black"

    @property
    def chess_color(self) -> chess.Color:
        return chess.WHITE if self is PlayerColor.WHITE else chess.BLACK


class Termination(StrEnum):
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVES = "fifty_moves"
    RESIGNATION = "resignation"
    DRAW_AGREED = "draw_agreed"


_FROM_CHESS_TERMINATION: dict[chess.Termination, Termination] = {
    chess.Termination.CHECKMATE: Termination.CHECKMATE,
    chess.Termination.STALEMATE: Termination.STALEMATE,
    chess.Termination.INSUFFICIENT_MATERIAL: Termination.INSUFFICIENT_MATERIAL,
    chess.Termination.THREEFOLD_REPETITION: Termination.THREEFOLD_REPETITION,
    chess.Termination.FIVEFOLD_REPETITION: Termination.THREEFOLD_REPETITION,
    chess.Termination.FIFTY_MOVES: Termination.FIFTY_MOVES,
    chess.Termination.SEVENTYFIVE_MOVES: Termination.FIFTY_MOVES,
}

DRAW = "1/2-1/2"

_FINISHED_TEXT: dict[Termination, str] = {
    Termination.CHECKMATE: "jaque mate",
    Termination.STALEMATE: "ahogado",
    Termination.INSUFFICIENT_MATERIAL: "material insuficiente",
    Termination.THREEFOLD_REPETITION: "triple repetición",
    Termination.FIFTY_MOVES: "regla de las 50 jugadas",
    Termination.RESIGNATION: "abandono",
    Termination.DRAW_AGREED: "tablas acordadas",
}

FULL_STRENGTH_OPTIONS: dict[str, int | bool] = {"UCI_LimitStrength": False, "Skill Level": 20}


class IllegalMoveError(ValueError):
    pass


class InvalidFenError(ValueError):
    """A start position that cannot be played. The message is user-facing (Spanish)."""


class DrawDecline(StrEnum):
    TOO_EARLY = "too_early"
    POSITION = "position"


@dataclass(frozen=True)
class Outcome:
    result: str  # "1-0", "0-1" or "1/2-1/2"
    termination: Termination


def board_from_moves(initial_fen: str, ucis: Sequence[str]) -> chess.Board:
    board = chess.Board(initial_fen)
    for uci in ucis:
        board.push_uci(uci)
    return board


def validate_start_fen(fen: str) -> str:
    """Check that `fen` is a legal, unfinished position and return it normalized."""
    try:
        board = chess.Board(fen.strip())
    except ValueError as exc:
        raise InvalidFenError("El FEN no tiene un formato válido.") from exc
    if not board.is_valid():
        raise InvalidFenError("La posición del FEN no es legal.")
    outcome = game_outcome(board)
    if outcome is not None:
        raise InvalidFenError(
            f"La posición ya está terminada ({_FINISHED_TEXT[outcome.termination]})."
        )
    return board.fen()


def parse_move(board: chess.Board, uci: str) -> chess.Move:
    """Parse a UCI move and check it is legal in `board`."""
    try:
        move = chess.Move.from_uci(uci)
    except ValueError as exc:
        raise IllegalMoveError(f"Invalid move format: {uci!r}") from exc
    if move not in board.legal_moves:
        raise IllegalMoveError(f"Illegal move in this position: {uci}")
    return move


def game_outcome(board: chess.Board) -> Outcome | None:
    """Outcome if the game is over.

    Threefold repetition and the 50-move rule end the game automatically, but only once they
    have actually happened on the board. (`board.outcome(claim_draw=True)` would also end it
    when the side to move merely *could* reach a repetition with its next move.)
    """
    outcome = board.outcome(claim_draw=False)
    if outcome is not None:
        termination = _FROM_CHESS_TERMINATION[outcome.termination]
        return Outcome(result=outcome.result(), termination=termination)
    if board.is_repetition(3):
        return Outcome(result=DRAW, termination=Termination.THREEFOLD_REPETITION)
    if board.is_fifty_moves():
        return Outcome(result=DRAW, termination=Termination.FIFTY_MOVES)
    return None


def resignation_outcome(player_color: PlayerColor) -> Outcome:
    result = "0-1" if player_color is PlayerColor.WHITE else "1-0"
    return Outcome(result=result, termination=Termination.RESIGNATION)


def plies_to_undo(by_bot: Sequence[bool]) -> int:
    """How many plies to take back so it is the player's turn again, before their last move.

    `by_bot[i]` tells whether ply i was played by the bot. Returns 0 if the player has not
    moved yet (e.g. only the bot's opening move as white exists).
    """
    if not by_bot:
        return 0
    if not by_bot[-1]:
        return 1  # The game ended right after the player's move.
    if len(by_bot) >= 2 and not by_bot[-2]:
        return 2
    return 0


def bot_search(
    preset: LevelPreset, movetime_s: float
) -> tuple[chess.engine.Limit, dict[str, int | bool]]:
    """Search limit and temporary UCI options that make the engine play at `preset`'s level."""
    limit = chess.engine.Limit(time=movetime_s, depth=preset.depth)
    options: dict[str, int | bool]
    if preset.uci_elo is not None:
        options = {"UCI_LimitStrength": True, "UCI_Elo": preset.uci_elo, "Skill Level": 20}
    elif preset.skill_level is not None:
        options = {"UCI_LimitStrength": False, "Skill Level": preset.skill_level}
    else:
        options = FULL_STRENGTH_OPTIONS
    return limit, options


def draw_too_early(board: chess.Board, min_fullmove: int) -> bool:
    """The bot never accepts a draw before move `min_fullmove`."""
    return board.fullmove_number < min_fullmove


def should_accept_draw(score: chess.engine.PovScore, bot_color: chess.Color, max_cp: int) -> bool:
    """The bot accepts if its own evaluation is at most `max_cp` centipawns."""
    return score.pov(bot_color).score(mate_score=MATE_SCORE_CP) <= max_cp


@dataclass(frozen=True)
class PgnData:
    white: str
    black: str
    played_on: date
    initial_fen: str
    ucis: Sequence[str]
    result: str | None  # None while the game is ongoing
    undo_count: int = 0
    hint_count: int = 0
    extra_headers: dict[str, str] = field(default_factory=dict)


def build_pgn(data: PgnData) -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = "whyfish"
    game.headers["Site"] = "whyfish"
    game.headers["Date"] = data.played_on.strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    game.headers["White"] = data.white
    game.headers["Black"] = data.black
    game.headers["Result"] = data.result or "*"
    game.headers["Termination"] = "normal" if data.result else "unterminated"
    if data.initial_fen != chess.STARTING_FEN:
        game.setup(chess.Board(data.initial_fen))
    if data.undo_count or data.hint_count:
        game.headers["Assists"] = f"undo:{data.undo_count} hint:{data.hint_count}"
    for key, value in data.extra_headers.items():
        game.headers[key] = value

    node: chess.pgn.GameNode = game
    for uci in data.ucis:
        node = node.add_variation(chess.Move.from_uci(uci))

    out = io.StringIO()
    print(game, file=out, end="\n")
    return out.getvalue()
