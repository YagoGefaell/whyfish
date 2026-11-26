"""Sacrifice detection (SPEC §3.1.2), shared by the classification and the explanation facts.

A move is a sacrifice when the mover ends up with less material than it had, and it did not
have to:

- the reference is the material the mover really has before the move: the balance with the
  pending exchanges resolved (quiescence), never the balance in the middle of an exchange;
- the move gives up at least `min_material` against that reference, either immediately
  (a piece left en prise: captures resolved right after the move) or along the played line
  (resolved after `horizon` plies extended through captures, and still at the end of the
  whole line);
- some other legal move keeps that material (resolved the same way). If every move loses it
  (e.g. in check, with a piece that cannot be saved), nothing is being sacrificed.

Pure: no engine calls, only the line already computed.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.analysis import material
from app.config import THRESHOLDS, ClassificationThresholds


@dataclass(frozen=True)
class Sacrifice:
    # Resolved material the mover had before the move and could have kept with another move.
    reference: int
    # Material given up against `reference` (>= min_material): the worst of the two measures.
    amount: int
    # Resolved balance right after the move (opponent to move) minus `reference`.
    after_move: int
    # Resolved balance along the played line minus `reference` (the better of the horizon and
    # the end of the whole line): < 0 means the mover is still down material at the end
    # ("material de menos"), >= 0 that it was recovered.
    line_end: int


def find_sacrifice(
    board: chess.Board,
    move: chess.Move,
    line: Sequence[str],
    t: ClassificationThresholds = THRESHOLDS,
) -> Sacrifice | None:
    """`line` is the played line in UCI, starting with `move` (only `move` is fine)."""
    mover = board.turn
    depth = t.quiescence_max_plies
    after_move = material.balance_after(board, move, mover, depth)
    horizon_end, full_end = _line_ends(board, move, line, t)
    # The loss must still be there at the end of the whole line, not only at the horizon (a
    # combination cut in the middle is not a sacrifice).
    line_end = max(
        material.resolved_balance(horizon_end, mover, depth),
        material.resolved_balance(full_end, mover, depth),
    )
    worst = min(after_move, line_end)
    before = material.resolved_balance(board, mover, depth)
    if before - worst < t.sacrifice_min_material:
        return None  # cheap exit before searching every alternative
    alternatives = [
        material.balance_after(board, m, mover, depth) for m in board.legal_moves if m != move
    ]
    if not alternatives:
        return None
    reference = min(before, max(alternatives))
    amount = reference - worst
    if amount < t.sacrifice_min_material:
        return None
    return Sacrifice(
        reference=reference,
        amount=amount,
        after_move=after_move - reference,
        line_end=line_end - reference,
    )


# Keep following a capture sequence this many plies past the horizon so the count does not
# stop in the middle of an exchange (the quiescence then settles what is left).
_EXCHANGE_EXTENSION = 4


def _line_ends(
    board: chess.Board, move: chess.Move, line: Sequence[str], t: ClassificationThresholds
) -> tuple[chess.Board, chess.Board]:
    """Positions after `horizon` plies of the line and at its end (valid moves only)."""
    ucis = list(line) if line and line[0] == move.uci() else [move.uci()]
    b = board.copy(stack=False)
    horizon = t.sacrifice_horizon_plies
    horizon_end: chess.Board | None = None
    for i, uci in enumerate(ucis):
        try:
            m = chess.Move.from_uci(uci)
        except ValueError:
            break
        if m not in b.legal_moves:
            break
        stop = i >= horizon and (i >= horizon + _EXCHANGE_EXTENSION or not b.is_capture(m))
        if stop and horizon_end is None:
            horizon_end = b.copy(stack=False)
        b.push(m)
    return horizon_end or b.copy(stack=False), b
