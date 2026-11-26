"""Sacrifice detection (SPEC §3.1.2), shared by the classification and the explanation facts.

A move is a sacrifice only when all of this holds:

1. **En prise:** after the move the opponent has a LEGAL capture of one of the mover's pieces
   whose SEE wins at least `min_material` (net of what the move itself captured). A piece that
   is merely attacked, without gain (e.g. by a king, on a defended square), is not given up.
2. **Resolved reference:** measured against the material the mover really has before the move
   (pending exchanges resolved by quiescence, never mid-exchange), the move loses at least
   `min_material` once the captures after it are resolved.
3. **Not forced:** some other legal move keeps that material (same measure). If every move
   loses it (e.g. in check, with a piece that cannot be saved), nothing is being sacrificed.
4. **Verified by the engine:** every legal capture of that piece must leave the mover with at
   least `brilliant_min_win_after`. A capture's evaluation comes from the engine line where it
   is played (the played move's MultiPV line, or one of the opponent's MultiPV lines after the
   move); a capture missing from the opponent's MultiPV (at least 2 lines) is worse for the
   opponent than the last line listed, whose evaluation is then a bound. A capture that cannot
   be checked either way means it is not a sacrifice.

Pure: no engine calls, only the evaluations already computed.
"""

from dataclasses import dataclass

import chess

from app.analysis import material
from app.analysis.types import PositionEval
from app.analysis.winprob import win_percent
from app.config import THRESHOLDS, ClassificationThresholds


@dataclass(frozen=True)
class Sacrifice:
    square: str  # square of the piece given up, after the move
    amount: int  # what the opponent wins by taking it (SEE, net of what the move captured)
    # The move and the opponent's capture, plus the rest of the engine line when the capture is
    # in one (UCI); score of that line from the mover's point of view (None for a bound).
    line: tuple[str, ...]
    cp: int | None
    mate: int | None
    # Mover's win% after the opponent's best capture (>= brilliant_min_win_after).
    win: float
    # True when the capture is not in the opponent's MultiPV: `win` is the bound given by the
    # last line listed (taking is worse for the opponent than any of them).
    bound: bool
    # Resolved balance at the end of the line minus the resolved reference before the move:
    # < 0 the mover is still down material there ("material de menos"), >= 0 recovered.
    # None for a bound (there is no line to follow).
    line_end: int | None


def find_sacrifice(
    board: chess.Board,
    move: chess.Move,
    before: PositionEval,
    after: PositionEval,
    t: ClassificationThresholds = THRESHOLDS,
) -> Sacrifice | None:
    """`before` / `after`: engine evaluations of `board` and of the position after `move`."""
    minimum = t.sacrifice_min_material
    en_prise = dict(material.left_en_prise(board, move, minimum))
    if not en_prise:
        return None
    mover = board.turn
    depth = t.quiescence_max_plies
    reference = material.resolved_balance(board, mover, depth)
    after_move = material.balance_after(board, move, mover, depth)
    if reference - after_move < minimum:
        return None
    alternatives = [
        material.balance_after(board, m, mover, depth) for m in board.legal_moves if m != move
    ]
    if not alternatives or max(alternatives) - after_move < minimum:
        return None  # every move loses it: forced, not a sacrifice
    after_board = board.copy(stack=False)
    after_board.push(move)
    for square in sorted(en_prise, key=lambda sq: -en_prise[sq]):
        captures = [
            m
            for m in after_board.legal_moves
            if m.to_square == square and after_board.is_capture(m)
        ]
        checked = [_evaluate(move, c, before, after) for c in captures]
        if not checked or any(v is None for v in checked):
            continue  # some capture cannot be checked
        verified = [v for v in checked if v is not None]
        worst = min(verified, key=lambda v: v.win)
        if worst.win < t.brilliant_min_win_after:
            continue
        shown = next((v for v in verified if not v.bound), worst)
        end = None if shown.bound else _resolved_end(board, shown.line, mover, depth) - reference
        return Sacrifice(
            square=chess.square_name(square),
            amount=en_prise[square],
            line=shown.line,
            cp=shown.cp,
            mate=shown.mate,
            win=worst.win,
            bound=shown.bound,
            line_end=end,
        )
    return None


@dataclass(frozen=True)
class _Checked:
    line: tuple[str, ...]
    cp: int | None
    mate: int | None
    win: float
    bound: bool


def _evaluate(
    move: chess.Move, capture: chess.Move, before: PositionEval, after: PositionEval
) -> _Checked | None:
    """Mover's evaluation after the opponent's `capture`, from the stored lines (or None)."""
    uci, reply = move.uci(), capture.uci()
    for line in before.lines:
        if line.move == uci and len(line.moves) > 1 and line.moves[1] == reply:
            return _Checked(line.moves, line.cp, line.mate, win_percent(line.cp, line.mate), False)
    for opp in after.lines:
        if opp.moves and opp.moves[0] == reply:
            cp, mate = _neg(opp.cp), _neg(opp.mate)
            return _Checked((uci, *opp.moves), cp, mate, win_percent(cp, mate), False)
    if len(after.lines) >= 2:
        last = after.lines[-1]
        bound = win_percent(_neg(last.cp), _neg(last.mate))
        return _Checked((uci, reply), None, None, bound, True)
    return None


def _neg(value: int | None) -> int | None:
    return -value if value is not None else None


def _resolved_end(board: chess.Board, line: tuple[str, ...], mover: chess.Color, depth: int) -> int:
    b = board.copy(stack=False)
    for uci in line:
        try:
            m = chess.Move.from_uci(uci)
        except ValueError:
            break
        if m not in b.legal_moves:
            break
        b.push(m)
    return material.resolved_balance(b, mover, depth)
