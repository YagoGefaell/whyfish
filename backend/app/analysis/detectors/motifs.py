"""Tactical motifs of a single move: fork, pin, discovered attack, double check.

Deflection, overload and x-ray are not detected yet (SPEC §4): they are hard to tell apart
from ordinary moves without false positives.
"""

from dataclasses import dataclass, replace
from typing import Literal

import chess

from app.analysis.detectors.common import PieceOn, require_piece
from app.analysis.material import PIECE_VALUES, see

MotifKind = Literal["fork", "pin", "discovered_attack", "double_check"]

_DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_ORTHOGONALS = ((1, 0), (-1, 0), (0, 1), (0, -1))
# A fork or a discovered attack only counts against pieces worth at least this (or the king).
_MIN_TARGET_VALUE = 3


@dataclass(frozen=True)
class Motif:
    kind: MotifKind
    # The piece that forks / pins / attacks (after the move; for a discovered attack, the
    # piece whose line was opened).
    by: PieceOn
    # Fork: the attacked pieces. Pin: (pinned piece, piece behind it). Discovered attack: the
    # newly attacked pieces. Double check: the king.
    targets: tuple[PieceOn, ...]
    # Ply of the line where the motif happens (0 for a single move).
    index: int = 0


def motifs_of_move(before: chess.Board, move: chess.Move) -> tuple[Motif, ...]:
    after = before.copy(stack=False)
    after.push(move)
    found: list[Motif] = []
    double = _double_check(after)
    if double:
        found.append(double)
    for detector in (_fork, _pin, _discovered):
        motif = detector(before, move, after)
        if motif:
            found.append(motif)
    return tuple(found)


def motifs_in_line(board: chess.Board, ucis: tuple[str, ...], plies: int) -> tuple[Motif, ...]:
    """Motifs of the first `plies` moves of a line, each tagged with its index."""
    b = board.copy(stack=False)
    found: list[Motif] = []
    for index, uci in enumerate(ucis[:plies]):
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            break
        found.extend(replace(m, index=index) for m in motifs_of_move(b, move))
        b.push(move)
    return tuple(found)


def _worth_attacking(after: chess.Board, square: chess.Square, attacker_value: int) -> bool:
    """A target that loses material when attacked: the king, a more valuable piece or an
    undefended one (worth at least a minor piece)."""
    piece = after.piece_at(square)
    if piece is None:
        return False
    if piece.piece_type == chess.KING:
        return True
    value = PIECE_VALUES[piece.piece_type]
    if value < _MIN_TARGET_VALUE:
        return False
    return value > attacker_value or not after.is_attacked_by(piece.color, square)


def _double_check(after: chess.Board) -> Motif | None:
    checkers = list(after.checkers())
    if len(checkers) < 2:
        return None
    king = after.king(after.turn)
    assert king is not None
    return Motif("double_check", require_piece(after, checkers[0]), (require_piece(after, king),))


def _fork(before: chess.Board, move: chess.Move, after: chess.Board) -> Motif | None:
    to = move.to_square
    moved = after.piece_at(to)
    assert moved is not None
    value = PIECE_VALUES[moved.piece_type] or 100
    targets = [
        s
        for s in after.attacks(to)
        if (p := after.piece_at(s)) is not None
        and p.color != moved.color
        and _worth_attacking(after, s, value)
    ]
    if len(targets) < 2 or see(after, to) > 0:
        return None  # a forking piece that can be won is not a fork
    ordered = sorted(targets, key=lambda s: -(PIECE_VALUES[after.piece_type_at(s) or 1] or 100))
    return Motif("fork", require_piece(after, to), tuple(require_piece(after, s) for s in ordered))


def _directions(piece_type: chess.PieceType) -> tuple[tuple[int, int], ...]:
    if piece_type == chess.BISHOP:
        return _DIAGONALS
    if piece_type == chess.ROOK:
        return _ORTHOGONALS
    if piece_type == chess.QUEEN:
        return _DIAGONALS + _ORTHOGONALS
    return ()


def _ray(square: chess.Square, df: int, dr: int) -> list[chess.Square]:
    out: list[chess.Square] = []
    f, r = chess.square_file(square) + df, chess.square_rank(square) + dr
    while 0 <= f < 8 and 0 <= r < 8:
        out.append(chess.square(f, r))
        f, r = f + df, r + dr
    return out


def _pin(before: chess.Board, move: chess.Move, after: chess.Board) -> Motif | None:
    """The moved slider pins an enemy piece to the king or to a more valuable piece."""
    to = move.to_square
    moved = after.piece_at(to)
    assert moved is not None
    if see(after, to) > 0:
        return None  # the pinning piece can be won
    for df, dr in _directions(moved.piece_type):
        pieces = [s for s in _ray(to, df, dr) if after.piece_at(s) is not None][:2]
        if len(pieces) < 2:
            continue
        first, second = (after.piece_at(s) for s in pieces)
        assert first is not None and second is not None
        if first.color == moved.color or second.color == moved.color:
            continue
        if first.piece_type == chess.KING or PIECE_VALUES[first.piece_type] < _MIN_TARGET_VALUE:
            continue
        behind_value = PIECE_VALUES[second.piece_type] or 100
        if behind_value > PIECE_VALUES[first.piece_type]:
            return Motif(
                "pin",
                require_piece(after, to),
                (require_piece(after, pieces[0]), require_piece(after, pieces[1])),
            )
    return None


def _discovered(before: chess.Board, move: chess.Move, after: chess.Board) -> Motif | None:
    """Moving a piece opens the line of another slider onto a valuable enemy piece."""
    mover = before.turn
    for square in (
        after.pieces(chess.BISHOP, mover)
        | after.pieces(chess.ROOK, mover)
        | after.pieces(chess.QUEEN, mover)
    ):
        if square == move.to_square:
            continue
        slider = after.piece_at(square)
        assert slider is not None
        value = PIECE_VALUES[slider.piece_type]
        targets = [
            t
            for t in after.attacks(square)
            if (p := after.piece_at(t)) is not None
            and p.color != mover
            and t not in before.attacks(square)
            and chess.BB_SQUARES[move.from_square] & chess.between(square, t)
            and _worth_attacking(after, t, value)
        ]
        if targets:
            return Motif(
                "discovered_attack",
                require_piece(after, square),
                tuple(require_piece(after, t) for t in targets),
            )
    return None
