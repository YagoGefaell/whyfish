"""On-demand evaluation of any position (exploring variations; coach tool in phase 6).

The response is plain facts computed by the engine and python-chess: scores, lines in UCI
and SAN, terminal status. Nothing here is free text, so it can be handed to an LLM as-is.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import chess
import chess.engine

from app.analysis.positions import engine_board, terminal_eval
from app.analysis.types import EngineLine
from app.analysis.winprob import line_win
from app.engine.pool import PoolManager

TerminalKind = Literal["checkmate", "stalemate", "draw"]


class EvaluationInputError(ValueError):
    """Invalid FEN or moves. The message is user-facing (Spanish)."""


@dataclass(frozen=True)
class EvaluatedLine:
    uci: tuple[str, ...]
    san: tuple[str, ...]
    cp: int | None  # side to move's point of view
    mate: int | None
    win: float  # side to move's win%


@dataclass(frozen=True)
class Evaluation:
    fen: str  # position evaluated (after `moves`)
    turn: chess.Color
    terminal: TerminalKind | None  # draw = repetition, 50 moves or insufficient material
    lines: tuple[EvaluatedLine, ...]  # best first; empty if terminal
    white_win: float  # for the eval bar
    white_cp: int | None
    white_mate: int | None


def build_board(fen: str, moves: Sequence[str]) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise EvaluationInputError("El FEN no tiene un formato válido.") from exc
    if not board.is_valid():
        raise EvaluationInputError("La posición del FEN no es legal.")
    for uci in moves:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise EvaluationInputError(f"Jugada no válida: {uci}") from exc
        if move not in board.legal_moves:
            raise EvaluationInputError(f"Jugada ilegal en esa posición: {uci}")
        board.push(move)
    return board


def _san_line(board: chess.Board, ucis: Sequence[str], plies: int) -> tuple[str, ...]:
    b = board.copy(stack=False)
    sans: list[str] = []
    for uci in ucis[:plies]:
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            break
        sans.append(b.san(move))
        b.push(move)
    return tuple(sans)


def describe(board: chess.Board, lines: Sequence[EngineLine], line_plies: int) -> Evaluation:
    """Pure: turn engine lines (or a terminal position) into an `Evaluation`."""
    terminal = terminal_eval(board)
    sign = 1 if board.turn == chess.WHITE else -1
    if terminal is not None:
        win = terminal.terminal_win
        assert win is not None
        kind: TerminalKind = "draw"
        if board.is_checkmate():
            kind = "checkmate"
        elif board.is_stalemate():
            kind = "stalemate"
        white_win = win if board.turn == chess.WHITE else 100 - win
        return Evaluation(board.fen(), board.turn, kind, (), white_win, None, None)
    evaluated = tuple(
        EvaluatedLine(
            uci=line.moves[:line_plies],
            san=_san_line(board, line.moves, line_plies),
            cp=line.cp,
            mate=line.mate,
            win=line_win(line),
        )
        for line in lines
    )
    best = evaluated[0]
    white_win = best.win if board.turn == chess.WHITE else 100 - best.win
    return Evaluation(
        fen=board.fen(),
        turn=board.turn,
        terminal=None,
        lines=evaluated,
        white_win=white_win,
        white_cp=best.cp * sign if best.cp is not None else None,
        white_mate=best.mate * sign if best.mate is not None else None,
    )


async def evaluate(
    pools: PoolManager,
    board: chess.Board,
    limit: chess.engine.Limit,
    multipv: int,
    line_plies: int,
) -> Evaluation:
    """Evaluate `board` (its move history is sent so the engine sees repetitions)."""
    if terminal_eval(board) is not None:
        return describe(board, (), line_plies)
    async with pools.use() as pool, pool.acquire() as engine:
        lines = await engine.analyse(engine_board(board), limit, multipv)
    return describe(board, lines, line_plies)
