"""Consequence point of a line (SPEC §5.3): where what makes a move bad (or good) materialises.

Shared by the level-1 text and "Ver por qué" (Phase 5), so both tell the same story. Pure.

Given the position before a move and a line starting with it:
- **mate:** the line reaches checkmate -> the mating ply;
- **material:** the material changes and settles: the first QUIET position (no profitable
  capture pending for the side to move, by quiescence) whose material already is the final
  balance (within a pawn when the swing is at least a piece) and from which the losing side
  never wins back more than that. It is never in the middle of an exchange: if the queen is
  taken and recaptured, the point is the recapture; later small trades do not move it.
  Promotions count as material;
- **none:** the material at the end is the same as at the start.

If the line ends before the position is quiet, the remaining captures are resolved by
quiescence; if that changes the final material (no earlier quiet position already had it),
the result is marked `settled=False` (Phase 5 extends such lines with the engine).
"""

from collections import Counter
from dataclasses import dataclass
from typing import Literal

import chess

from app.analysis import material
from app.config import FACTS, FactThresholds

Kind = Literal["mate", "material", "none"]

_NAMES: dict[chess.PieceType, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
}


@dataclass(frozen=True)
class Consequence:
    kind: Kind
    # Index in the line of the consequence ply (0 = the first move); None for "none", or
    # when it lies beyond the end of the line (not settled).
    ply: int | None
    # Mover's material change from the start of the line to that point (P=1 ... Q=9); with
    # `settled=False`, the change once the captures pending at the end are resolved.
    material: int
    # Pieces each side lost up to that point, after cancelling equal trades ("pawn", ...),
    # biggest first. Promotions appear in `promoted` (the mover's / the opponent's).
    lost: tuple[str, ...]
    won: tuple[str, ...]
    promoted: tuple[str, ...]  # pieces the mover promoted to
    opponent_promoted: tuple[str, ...]
    # The mated side in a "mate" consequence: True if it is the mover.
    mover_mated: bool
    settled: bool  # the point is inside the line (no captures left to resolve beyond it)


def consequence(
    board: chess.Board, ucis: tuple[str, ...], t: FactThresholds = FACTS
) -> Consequence:
    """`board`: position before the line; `ucis`: the line (invalid moves cut it short)."""
    mover = board.turn
    b = board.copy(stack=False)
    start = material.balance(b, mover)
    depth = t.quiescence_max_plies
    # Static balance and quietness after each ply; what was captured / promoted at each ply.
    values: list[int] = []
    quiet: list[bool] = []
    events: list[tuple[chess.Color, chess.PieceType | None, chess.PieceType | None]] = []
    for uci in ucis[: t.consequence_max_plies]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in b.legal_moves:
            break
        captured = _captured_type(b, move)
        events.append((b.turn, captured, move.promotion))
        b.push(move)
        if b.is_checkmate():
            mover_mated = b.turn == mover
            return _result("mate", len(events) - 1, mover, events, True, mover_mated=mover_mated)
        static = material.balance(b, mover)
        values.append(static)
        quiet.append(material.resolved_balance(b, mover, depth) == static)

    end_static = material.balance(b, mover)
    end_resolved = material.resolved_balance(b, mover, depth)
    end_quiet = quiet[-1] if values else end_resolved == end_static
    final = end_static if end_quiet else end_resolved
    if final == start:
        return Consequence("none", None, 0, (), (), (), (), False, end_quiet)
    point = _point(values, quiet, start, final)
    if point is None:
        return _result("material", None, mover, events, False, material_=final - start)
    # Settled at `point` even if the line goes on with smaller trades or ends in the middle of
    # a later (even) exchange.
    return _result("material", point, mover, events[: point + 1], True)


def _point(values: list[int], quiet: list[bool], start: int, final: int) -> int | None:
    """First quiet ply whose material already is the final balance (within one pawn when the
    swing is at least a piece) and from which the losing side never wins back more than that
    tolerance. Later small trades do not move the story's end."""
    direction = 1 if final > start else -1
    tolerance = 1 if abs(final - start) >= 3 else 0
    for i, value in enumerate(values):
        if not quiet[i] or (value - start) * direction <= 0 or abs(value - final) > tolerance:
            continue
        later = [values[j] for j in range(i + 1, len(values)) if quiet[j]]
        if all((v - value) * -direction <= tolerance for v in later):
            return i
    return None


def _captured_type(board: chess.Board, move: chess.Move) -> chess.PieceType | None:
    if board.is_en_passant(move):
        return chess.PAWN
    piece = board.piece_at(move.to_square)
    return piece.piece_type if piece and board.is_capture(move) else None


def _result(
    kind: Kind,
    ply: int | None,
    mover: chess.Color,
    events: list[tuple[chess.Color, chess.PieceType | None, chess.PieceType | None]],
    settled: bool,
    *,
    mover_mated: bool = False,
    material_: int | None = None,
) -> Consequence:
    won: Counter[chess.PieceType] = Counter()
    lost: Counter[chess.PieceType] = Counter()
    promoted: list[str] = []
    opponent_promoted: list[str] = []
    for color, captured, promotion in events:
        if captured is not None:
            (won if color == mover else lost)[captured] += 1
        if promotion is not None:
            (promoted if color == mover else opponent_promoted).append(_NAMES[promotion])
    for kind_ in list(won):
        common = min(won[kind_], lost[kind_])
        won[kind_] -= common
        lost[kind_] -= common
    if material_ is None:
        # Material at the point, from what was captured and promoted up to it.
        material_ = sum(material.PIECE_VALUES[k] * n for k, n in won.items()) - sum(
            material.PIECE_VALUES[k] * n for k, n in lost.items()
        )
        material_ += sum(material.PIECE_VALUES[_type(p)] - 1 for p in promoted)
        material_ -= sum(material.PIECE_VALUES[_type(p)] - 1 for p in opponent_promoted)
    return Consequence(
        kind=kind,
        ply=ply,
        material=material_,
        lost=_sorted(lost),
        won=_sorted(won),
        promoted=tuple(promoted),
        opponent_promoted=tuple(opponent_promoted),
        mover_mated=mover_mated,
        settled=settled,
    )


def _type(name: str) -> chess.PieceType:
    return next(k for k, v in _NAMES.items() if v == name)


def _sorted(counter: Counter[chess.PieceType]) -> tuple[str, ...]:
    pieces = [k for k, n in counter.items() for _ in range(n)]
    pieces.sort(key=lambda k: -material.PIECE_VALUES[k])
    return tuple(_NAMES[k] for k in pieces)
