"""Positions of a game as the engine sees them, and their cache keys. Pure."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.analysis.types import PositionEval
from app.play.rules import game_outcome


@dataclass(frozen=True)
class GamePosition:
    ply: int  # number of moves played before this position
    board: chess.Board  # with only the reversible history (see `engine_board`)
    key: str  # cache key: depends on exactly what the engine is given
    terminal: PositionEval | None  # set for finished positions (no engine needed)


def engine_board(board: chess.Board) -> chess.Board:
    """`board` with its history cut at the last irreversible move (capture, pawn move, ...).

    Earlier positions can never repeat, so this keeps everything the engine needs to detect
    repetitions while letting different games share cache entries.
    """
    tail: list[chess.Move] = []
    probe = board.copy()
    while probe.move_stack:
        move = probe.pop()
        if probe.is_irreversible(move):
            probe.push(move)
            break
        tail.append(move)
    root = chess.Board(probe.fen())
    for move in reversed(tail):
        root.push(move)
    return root


def position_key(board: chess.Board) -> str:
    """Hash of the root FEN (without the move number, which engines ignore) + the moves."""
    root = board.root()
    root_fen = " ".join(root.fen().split()[:5])
    text = root_fen + "|" + " ".join(m.uci() for m in board.move_stack)
    return hashlib.sha1(text.encode()).hexdigest()


def terminal_eval(board: chess.Board) -> PositionEval | None:
    """Value of a finished position for the side to move, or None if the game goes on."""
    if board.is_checkmate():
        return PositionEval(terminal_win=0.0)
    if game_outcome(board) is not None:
        return PositionEval(terminal_win=50.0)
    return None


def game_positions(initial_fen: str, ucis: Sequence[str]) -> list[GamePosition]:
    """Every position of the game (start + after each move)."""
    full = chess.Board(initial_fen)
    boards = [full.copy()]
    for uci in ucis:
        full.push_uci(uci)
        boards.append(full.copy())
    result = []
    for ply, b in enumerate(boards):
        eb = engine_board(b)
        result.append(
            GamePosition(ply=ply, board=eb, key=position_key(eb), terminal=terminal_eval(b))
        )
    return result
