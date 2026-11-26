"""Threats, hanging pieces and parried threats.

A threat of `color` is what it could win if it were its turn (the other side passed): material
won by SEE on an enemy piece, or a mate in one.
"""

from dataclasses import dataclass
from typing import Literal

import chess

from app.analysis import material
from app.analysis.detectors.common import (
    PieceOn,
    as_side_to_move,
    by_value,
    piece_on,
    require_piece,
)


@dataclass(frozen=True)
class Threat:
    kind: Literal["capture", "mate"]
    # Capture: the piece that can be won and how much (SEE). Mate: target is the king.
    target: PieceOn
    gain: int
    # Squares of the pieces that start the capture (least valuable first) or give mate.
    attackers: tuple[str, ...]
    # The capture or mating move, UCI (for arrows).
    move: str


@dataclass(frozen=True)
class Hanging:
    """A piece of the mover that the opponent can win (SEE) after the move."""

    piece: PieceOn
    loss: int  # net of what the move itself captured
    attackers: tuple[str, ...]  # least valuable first


@dataclass(frozen=True)
class Parried:
    """An opponent threat that existed before the move and no longer does."""

    threat: Threat
    how: Literal["moved", "captured_attacker", "defended", "mate_stopped"]
    # Where the threatened piece is after the move (it may have moved).
    piece_after: PieceOn | None


def capture_threats(board: chess.Board, color: chess.Color, min_gain: int) -> tuple[Threat, ...]:
    """Enemy pieces `color` could win at least `min_gain` from, biggest gain first."""
    b = as_side_to_move(board, color)
    found: list[Threat] = []
    for square, piece in b.piece_map().items():
        if piece.color == color or piece.piece_type == chess.KING:
            continue
        gain = material.see(b, square)
        if gain < min_gain:
            continue
        captures = [m for m in b.legal_moves if m.to_square == square]
        if not captures:
            continue
        attackers = by_value(b, chess.SquareSet(m.from_square for m in captures))
        first = next(m for m in captures if chess.square_name(m.from_square) == attackers[0])
        found.append(Threat("capture", require_piece(b, square), gain, attackers, first.uci()))
    found.sort(key=lambda t: (-t.gain, t.target.square))
    return tuple(found)


def mate_threat(board: chess.Board, color: chess.Color) -> Threat | None:
    """A mate in one `color` would have if it were its turn."""
    b = as_side_to_move(board, color)
    king = b.king(not color)
    if king is None:
        return None
    for move in b.legal_moves:
        b.push(move)
        mate = b.is_checkmate()
        b.pop()
        if mate:
            return Threat(
                "mate",
                require_piece(b, king),
                0,
                (chess.square_name(move.from_square),),
                move.uci(),
            )
    return None


def new_threats(before: chess.Board, move: chess.Move, min_gain: int) -> tuple[Threat, ...]:
    """Threats the move itself creates: new (or bigger) threats of the mover after `move`
    whose attack comes from the moved piece or from a line the move opened.

    Nothing when the mover was in check: threats "appear" just because the check is gone.
    """
    if before.is_check():
        return ()
    mover = before.turn
    after = before.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        return ()
    old = {t.target.square: t.gain for t in capture_threats(before, mover, min_gain)}
    result = [
        t
        for t in capture_threats(after, mover, min_gain)
        if t.gain > old.get(t.target.square, 0) and _caused_by(move, t)
    ]
    mate = mate_threat(after, mover)
    if mate is not None and not after.is_check() and mate_threat(before, mover) is None:
        result.insert(0, mate)
    return tuple(result)


def _caused_by(move: chess.Move, threat: Threat) -> bool:
    """The threat's first attacker is the moved piece or attacks through the vacated square."""
    attacker = chess.parse_square(threat.attackers[0])
    if attacker == move.to_square:
        return True
    target = chess.parse_square(threat.target.square)
    return bool(chess.BB_SQUARES[move.from_square] & chess.between(attacker, target))


def hanging_after(before: chess.Board, move: chess.Move, min_gain: int) -> tuple[Hanging, ...]:
    """Pieces of the mover that `move` leaves en prise (see `material.left_en_prise`)."""
    after = before.copy(stack=False)
    after.push(move)
    result: list[Hanging] = []
    for square, loss in material.left_en_prise(before, move, min_gain):
        piece = require_piece(after, square)
        attackers = by_value(after, after.attackers(after.turn, square))
        result.append(Hanging(piece, loss, attackers))
    result.sort(key=lambda h: (-h.loss, h.piece.square))
    return tuple(result)


def parried_threats(before: chess.Board, move: chess.Move, min_gain: int) -> tuple[Parried, ...]:
    """Opponent threats against the mover that `move` removes.

    Not computed when the mover is in check (answering a check is not "parrying a threat").
    A threatened piece counts as safe only if it is still on the board (not traded off).
    """
    if before.is_check():
        return ()
    mover = before.turn
    opponent = not mover
    after = before.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        return ()
    still = {t.target.square for t in capture_threats(after, opponent, min_gain)}
    result: list[Parried] = []
    for threat in capture_threats(before, opponent, min_gain):
        origin = chess.parse_square(threat.target.square)
        moved = move.from_square == origin
        new_square = move.to_square if moved else origin
        piece_after = piece_on(after, new_square)
        if piece_after is None or piece_after.color != threat.target.color:
            continue  # the piece was lost
        if piece_after.piece != threat.target.piece and move.promotion is None:
            continue
        if piece_after.square in still:
            continue
        if moved:
            how: Literal["moved", "captured_attacker", "defended"] = "moved"
        elif chess.square_name(move.to_square) in threat.attackers:
            how = "captured_attacker"
        else:
            how = "defended"
        result.append(Parried(threat, how, piece_after))
    mate = mate_threat(before, opponent)
    if mate is not None and mate_threat(after, opponent) is None:
        result.insert(0, Parried(mate, "mate_stopped", None))
    return tuple(result)
