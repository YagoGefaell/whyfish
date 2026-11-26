"""Move classification (SPEC §3). Pure: works on boards and precomputed engine evaluations.

Evaluation order: book -> missed opportunity -> brilliant -> great -> best -> Δ thresholds.
All win% values are from the mover's point of view.
"""

from dataclasses import dataclass

import chess

from app.analysis import material
from app.analysis.sacrifice import find_sacrifice
from app.analysis.types import Classification, PositionEval
from app.analysis.winprob import MATE_SCORE, line_score, line_win, move_accuracy, position_win
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
    if inp.in_book and delta < t.book_max_delta:
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
        and not_behind(inp.board, t)
        and is_sacrifice(inp, t)
    ):
        return C.BRILLIANT
    best = is_best(inp)
    gap = score_gap(inp) if decided(wb, t) else None
    if (
        best
        and special
        and wb < t.great_max_win_before
        and not gives_mate(inp.board, inp.move)
        and not takes_free_material(inp.board, inp.move)
        and is_great(inp.before, t)
    ):
        return C.GREAT
    equal = delta < t.equal_max_delta and (gap is None or gap < t.decided_equal_max_cp)
    if best or equal:
        return C.BEST
    by_delta = _by_delta(delta, t)
    if gap is None or gap < t.decided_equal_max_cp:
        return by_delta
    # Decided position: win% says (almost) nothing; the score keeps the move from being ★.
    cap = C.EXCELLENT if gap < t.decided_excellent_max_cp else C.GOOD
    return max(by_delta, cap, key=_ORDER.index)


_ORDER = [C.BEST, C.EXCELLENT, C.GOOD, C.INACCURACY, C.MISTAKE, C.BLUNDER]


def _by_delta(delta: float, t: ClassificationThresholds) -> Classification:
    if delta < t.excellent:
        return C.EXCELLENT
    if delta < t.good:
        return C.GOOD
    if delta < t.inaccuracy:
        return C.INACCURACY
    if delta < t.mistake:
        return C.MISTAKE
    return C.BLUNDER


def not_behind(board: chess.Board, t: ClassificationThresholds) -> bool:
    """The mover is not already down material (pending exchanges resolved)."""
    resolved = material.resolved_balance(board, board.turn, t.quiescence_max_plies)
    return resolved >= t.brilliant_min_material_before


def takes_free_material(board: chess.Board, move: chess.Move) -> bool:
    """The move captures something the opponent left en prise: it wins material even after the
    opponent's best recapture sequence (SEE). Punishing an obvious error is not great (★)."""
    if not board.is_capture(move):
        return False
    after = board.copy(stack=False)
    after.push(move)
    return material.captured_value(board, move) - material.see(after, move.to_square) >= 1


def decided(win: float, t: ClassificationThresholds) -> bool:
    """The game is (nearly) decided for one side: win% saturates there."""
    return win > t.decided_above or win < 100.0 - t.decided_above


def move_score(inp: MoveInput) -> int | None:
    """Score (cp-equivalent) of the played move for the mover, from the same data as its win%."""
    uci = inp.move.uci()
    for line in inp.before.lines:
        if line.move == uci:
            return line_score(line)
    if inp.after.lines:
        return -line_score(inp.after.lines[0])
    after = inp.board.copy(stack=False)
    after.push(inp.move)
    if after.is_checkmate():
        return MATE_SCORE
    return 0 if after.is_game_over() else None


def score_gap(inp: MoveInput) -> int | None:
    """How much worse than the best line the played move scores (cp), if both are known."""
    if not inp.before.lines:
        return None
    played = move_score(inp)
    return None if played is None else max(0, line_score(inp.before.lines[0]) - played)


def equal_moves(before: PositionEval, t: ClassificationThresholds = THRESHOLDS) -> tuple[str, ...]:
    """Other MultiPV moves as good as the best one (UCI, in MultiPV order): Δ win% below
    `equal_max_delta` and, in a decided position, a score within `decided_equal_max_cp`."""
    if len(before.lines) < 2:
        return ()
    top = before.lines[0]
    top_win = line_win(top)
    out: list[str] = []
    for line in before.lines[1:]:
        if not line.moves or top_win - line_win(line) >= t.equal_max_delta:
            continue
        if decided(top_win, t) and line_score(top) - line_score(line) >= t.decided_equal_max_cp:
            continue
        out.append(line.move)
    return tuple(out)


def is_best(inp: MoveInput) -> bool:
    return bool(inp.before.lines) and inp.before.lines[0].move == inp.move.uci()


def gives_mate(board: chess.Board, move: chess.Move) -> bool:
    """Mate in one is never a great move: it is simply the best (SPEC §3.2)."""
    after = board.copy(stack=False)
    after.push(move)
    return after.is_checkmate()


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
    """SPEC §3.1.2: see `app.analysis.sacrifice`."""
    return find_sacrifice(inp.board, inp.move, inp.before, inp.after, t) is not None
