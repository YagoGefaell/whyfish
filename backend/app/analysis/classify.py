"""Move classification (SPEC §3). Pure: works on boards and precomputed engine evaluations.

Evaluation order: book -> missed opportunity -> brilliant -> great -> best -> Δ thresholds.
All win% values are from the mover's point of view.
"""

from dataclasses import dataclass

import chess

from app.analysis import material
from app.analysis.types import Classification, PositionEval
from app.analysis.winprob import line_win, move_accuracy, position_win
from app.config import THRESHOLDS, ClassificationThresholds

C = Classification


@dataclass(frozen=True)
class MoveInput:
    board: chess.Board  # position before the move, with its move history
    move: chess.Move
    before: PositionEval  # engine view of `board`
    after: PositionEval  # engine view of the position after `move`
    in_book: bool  # the position after `move` is in the opening book
    previous: Classification | None  # classification of the opponent's previous move


@dataclass(frozen=True)
class MoveVerdict:
    classification: Classification
    win_before: float
    win_after: float
    delta: float
    accuracy: float


def win_after(inp: MoveInput) -> float:
    """Mover's win% after the move.

    If the move is one of the MultiPV lines, use that line's score (same search as the "before"
    value, so the best move has Δ = 0 exactly); otherwise use the next position's evaluation.
    """
    uci = inp.move.uci()
    for line in inp.before.lines:
        if line.move == uci:
            return line_win(line)
    return 100.0 - position_win(inp.after)


def classify(inp: MoveInput, t: ClassificationThresholds = THRESHOLDS) -> MoveVerdict:
    wb = position_win(inp.before)
    wa = win_after(inp)
    delta = max(0.0, wb - wa)
    return MoveVerdict(
        classification=_classification(inp, wb, wa, delta, t),
        win_before=wb,
        win_after=wa,
        delta=delta,
        accuracy=move_accuracy(wb, wa),
    )


def _classification(
    inp: MoveInput, wb: float, wa: float, delta: float, t: ClassificationThresholds
) -> Classification:
    if inp.in_book:
        return C.BOOK
    if (
        inp.previous in (C.MISTAKE, C.BLUNDER)
        and delta >= t.missed_min_delta
        and wb >= t.missed_decisive_win
    ):
        return C.MISS
    special = not is_only_move(inp.board) and not is_obvious_recapture(inp.board, inp.move)
    if (
        special
        and delta < t.brilliant_max_delta
        and wb < t.brilliant_max_win_before
        and wa >= t.brilliant_min_win_after
        and is_sacrifice(inp, t)
    ):
        return C.BRILLIANT
    best = is_best(inp)
    if best and special and is_great(inp.before, t):
        return C.GREAT
    if best or delta <= t.best_max_delta:
        return C.BEST
    if delta < t.excellent:
        return C.EXCELLENT
    if delta < t.good:
        return C.GOOD
    if delta < t.inaccuracy:
        return C.INACCURACY
    if delta < t.mistake:
        return C.MISTAKE
    return C.BLUNDER


def is_best(inp: MoveInput) -> bool:
    return bool(inp.before.lines) and inp.before.lines[0].move == inp.move.uci()


def is_only_move(board: chess.Board) -> bool:
    return board.legal_moves.count() == 1


def is_obvious_recapture(board: chess.Board, move: chess.Move) -> bool:
    """A capture on the square where the opponent has just captured."""
    if not board.move_stack or not board.is_capture(move):
        return False
    previous = board.copy()
    last = previous.pop()
    return previous.is_capture(last) and last.to_square == move.to_square


def outcome_category(win: float, t: ClassificationThresholds) -> int:
    """-1 losing, 0 balanced, 1 winning."""
    if win > t.winning_above:
        return 1
    if win < t.losing_below:
        return -1
    return 0


def is_great(before: PositionEval, t: ClassificationThresholds) -> bool:
    """The best move is clearly better than the second option (SPEC §3.2 a/b)."""
    if len(before.lines) < 2:
        return False
    first, second = line_win(before.lines[0]), line_win(before.lines[1])
    if first - second >= t.great_min_gap:
        return True
    return outcome_category(first, t) != outcome_category(second, t)


def is_sacrifice(inp: MoveInput, t: ClassificationThresholds) -> bool:
    """SPEC §3.1.2: material drops along the line, or a piece of ours is newly en prise."""
    if material.newly_en_prise(inp.board, inp.move, t.sacrifice_min_material):
        return True
    line = _played_line(inp)
    return _material_drop(inp.board, line, t.sacrifice_horizon_plies) >= t.sacrifice_min_material


def _played_line(inp: MoveInput) -> tuple[str, ...]:
    uci = inp.move.uci()
    for line in inp.before.lines:
        if line.move == uci:
            return line.moves
    reply = inp.after.lines[0].moves if inp.after.lines else ()
    return (uci, *reply)


# Keep following a capture sequence this many plies past the horizon so the count does not
# stop in the middle of an exchange.
_EXCHANGE_EXTENSION = 4


def _material_drop(board: chess.Board, line: tuple[str, ...], horizon: int) -> int:
    """How much material the side to move in `board` is down after `horizon` plies of `line`."""
    mover = board.turn
    b = board.copy(stack=False)
    start = material.balance(b, mover)
    limit = horizon + _EXCHANGE_EXTENSION
    for i, uci in enumerate(line):
        if i >= horizon:
            if i >= limit:
                break
            if not b.is_capture(chess.Move.from_uci(uci)):
                break
        try:
            b.push_uci(uci)
        except ValueError:
            break
    return start - material.balance(b, mover)
