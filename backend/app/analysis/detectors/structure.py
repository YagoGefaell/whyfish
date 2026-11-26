"""Positional facts: game phase, pawn structure changes, king shield, development. Pure."""

from dataclasses import dataclass
from typing import Literal

import chess

from app.analysis.detectors.common import color_name
from app.analysis.material import PIECE_VALUES
from app.config import FACTS, FactThresholds

Phase = Literal["opening", "middlegame", "endgame"]
PawnChangeKind = Literal["doubled", "isolated", "passed", "opponent_passed"]

_MINOR_HOMES: dict[chess.Color, dict[chess.PieceType, chess.SquareSet]] = {
    chess.WHITE: {
        chess.KNIGHT: chess.SquareSet([chess.B1, chess.G1]),
        chess.BISHOP: chess.SquareSet([chess.C1, chess.F1]),
    },
    chess.BLACK: {
        chess.KNIGHT: chess.SquareSet([chess.B8, chess.G8]),
        chess.BISHOP: chess.SquareSet([chess.C8, chess.F8]),
    },
}


@dataclass(frozen=True)
class PawnChange:
    kind: PawnChangeKind
    color: str  # whose pawn it is
    where: str  # a file letter ("f") for doubled / isolated, a square for passed pawns


def phase(board: chess.Board, t: FactThresholds = FACTS) -> Phase:
    pieces = sum(
        PIECE_VALUES[p.piece_type]
        for p in board.piece_map().values()
        if p.piece_type not in (chess.PAWN, chess.KING)
    )
    if pieces <= t.endgame_max_material:
        return "endgame"
    if board.fullmove_number <= t.opening_max_fullmove:
        return "opening"
    return "middlegame"


def _files(board: chess.Board, color: chess.Color) -> list[int]:
    """Number of pawns of `color` on each file."""
    counts = [0] * 8
    for square in board.pieces(chess.PAWN, color):
        counts[chess.square_file(square)] += 1
    return counts


def doubled_files(board: chess.Board, color: chess.Color) -> set[int]:
    return {f for f, n in enumerate(_files(board, color)) if n >= 2}


def isolated_files(board: chess.Board, color: chess.Color) -> set[int]:
    counts = _files(board, color)
    return {
        f
        for f, n in enumerate(counts)
        if n and (f == 0 or not counts[f - 1]) and (f == 7 or not counts[f + 1])
    }


def passed_pawns(board: chess.Board, color: chess.Color) -> set[chess.Square]:
    enemy = board.pieces(chess.PAWN, not color)
    result: set[chess.Square] = set()
    for square in board.pieces(chess.PAWN, color):
        f, r = chess.square_file(square), chess.square_rank(square)
        ahead = range(r + 1, 8) if color == chess.WHITE else range(0, r)
        blockers = [
            s for s in enemy if abs(chess.square_file(s) - f) <= 1 and chess.square_rank(s) in ahead
        ]
        if not blockers:
            result.add(square)
    return result


def pawn_changes(before: chess.Board, move: chess.Move) -> tuple[PawnChange, ...]:
    """Pawn weaknesses the move gives the mover and passed pawns it creates for either side."""
    mover = before.turn
    after = before.copy(stack=False)
    after.push(move)
    changes: list[PawnChange] = []
    for f in sorted(doubled_files(after, mover) - doubled_files(before, mover)):
        changes.append(PawnChange("doubled", color_name(mover), chess.FILE_NAMES[f]))
    for f in sorted(isolated_files(after, mover) - isolated_files(before, mover)):
        changes.append(PawnChange("isolated", color_name(mover), chess.FILE_NAMES[f]))
    was_passed = passed_pawns(before, mover)
    for s in sorted(passed_pawns(after, mover)):
        origin = move.from_square if s == move.to_square else s
        if origin not in was_passed:
            changes.append(PawnChange("passed", color_name(mover), chess.square_name(s)))
    for s in sorted(passed_pawns(after, not mover) - passed_pawns(before, not mover)):
        changes.append(PawnChange("opponent_passed", color_name(not mover), chess.square_name(s)))
    return tuple(changes)


def weakens_king(before: chess.Board, move: chess.Move) -> bool:
    """A pawn of the shield in front of a castled king (wing files, back rank) moves forward."""
    mover = before.turn
    king = before.king(mover)
    piece = before.piece_at(move.from_square)
    if king is None or piece is None or piece.piece_type != chess.PAWN:
        return False
    back = 0 if mover == chess.WHITE else 7
    king_file = chess.square_file(king)
    if chess.square_rank(king) != back or king_file in (3, 4):
        return False  # not castled (or castled-like) on a wing
    pawn_file = chess.square_file(move.from_square)
    shield_ranks = (1, 2) if mover == chess.WHITE else (6, 5)
    return abs(pawn_file - king_file) <= 1 and chess.square_rank(move.from_square) in shield_ranks


def develops(before: chess.Board, move: chess.Move, t: FactThresholds = FACTS) -> bool:
    """In the opening, a knight or bishop leaves its starting square."""
    if phase(before, t) != "opening":
        return False
    piece = before.piece_at(move.from_square)
    if piece is None or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    return move.from_square in _MINOR_HOMES[piece.color][piece.piece_type]
