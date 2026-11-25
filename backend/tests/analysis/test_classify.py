"""Classification rules with hand-written engine evaluations (deterministic)."""

import chess
import pytest

from app.analysis.classify import (
    MoveInput,
    _material_drop,
    classify,
    is_obvious_recapture,
    is_sacrifice,
)
from app.analysis.types import Classification as C
from app.analysis.types import EngineLine, PositionEval
from app.config import THRESHOLDS


def ev(*lines: tuple[str, int]) -> PositionEval:
    """Lines as (space-separated UCI moves, cp from the side to move's point of view)."""
    return PositionEval(lines=tuple(EngineLine(tuple(m.split()), cp=cp) for m, cp in lines))


def mate_ev(moves: str, mate: int) -> PositionEval:
    return PositionEval(lines=(EngineLine(tuple(moves.split()), mate=mate),))


NEUTRAL_AFTER = ev(("e7e5", 0))


def inp(
    fen: str,
    move: str,
    before: PositionEval,
    after: PositionEval = NEUTRAL_AFTER,
    history: tuple[str, ...] = (),
    previous: C | None = None,
    in_book: bool = False,
) -> MoveInput:
    board = chess.Board(fen)
    for uci in history:
        board.push_uci(uci)
    return MoveInput(board, chess.Move.from_uci(move), before, after, in_book, previous)


START = chess.STARTING_FEN


def test_book_wins_over_everything() -> None:
    verdict = classify(inp(START, "a2a3", ev(("e2e4", 0), ("a2a3", -300)), in_book=True))
    assert verdict.classification is C.BOOK


@pytest.mark.parametrize(
    ("cp", "expected"),
    [
        (-20, C.EXCELLENT),  # Δ 1.8
        (-50, C.GOOD),  # Δ 4.6
        (-100, C.INACCURACY),  # Δ 9.1
        (-200, C.MISTAKE),  # Δ 17.6
        (-300, C.BLUNDER),  # Δ 25.1
    ],
)
def test_delta_thresholds(cp: int, expected: C) -> None:
    verdict = classify(inp(START, "a2a3", ev(("e2e4", 0), ("a2a3", cp))))
    assert verdict.classification is expected
    assert verdict.win_before == 50.0


def test_move_outside_multipv_uses_next_position_eval() -> None:
    # After 1.h4 black (to move) is +100 from its point of view -> white lost ~9.1 points.
    verdict = classify(inp(START, "h2h4", ev(("e2e4", 0), ("d2d4", 0)), after=ev(("e7e5", 100))))
    assert verdict.win_after == pytest.approx(100 - 59.10, abs=0.01)
    assert verdict.classification is C.INACCURACY


def test_delta_is_never_negative() -> None:
    verdict = classify(inp(START, "h2h4", ev(("e2e4", 0)), after=ev(("e7e5", -100))))
    assert verdict.delta == 0.0
    assert verdict.classification is C.BEST


class TestBestAndGreat:
    def test_best_with_a_close_second(self) -> None:
        verdict = classify(inp(START, "e2e4", ev(("e2e4", 30), ("d2d4", 25))))
        assert verdict.classification is C.BEST
        assert verdict.delta == 0.0

    def test_equal_alternative_is_also_best(self) -> None:
        assert classify(inp(START, "d2d4", ev(("e2e4", 30), ("d2d4", 30)))).classification is C.BEST

    def test_great_when_second_option_is_10_points_worse(self) -> None:
        verdict = classify(inp(START, "e2e4", ev(("e2e4", 0), ("d2d4", -200))))
        assert verdict.classification is C.GREAT

    def test_great_when_second_option_changes_outcome_category(self) -> None:
        # +300 = 75.1% (winning) vs +250 = 70.7% (balanced): gap < 10 but crosses 75%.
        verdict = classify(inp(START, "e2e4", ev(("e2e4", 300), ("d2d4", 250))))
        assert verdict.classification is C.GREAT

    def test_not_great_with_a_single_line(self) -> None:
        assert classify(inp(START, "e2e4", ev(("e2e4", 0)))).classification is C.BEST

    def test_only_legal_move_is_never_great(self) -> None:
        fen = "7k/8/8/8/8/8/6q1/7K w - - 0 1"  # Kxg2 is forced
        assert chess.Board(fen).legal_moves.count() == 1
        verdict = classify(inp(fen, "h1g2", ev(("h1g2", 0))))
        assert verdict.classification is C.BEST

    def test_obvious_recapture_is_never_great(self) -> None:
        # 1.e4 d5 2.exd5 Qxd5: recapture on d5, even if everything else loses a pawn.
        verdict = classify(
            inp(START, "d8d5", ev(("d8d5", 0), ("g8f6", -150)), history=("e2e4", "d7d5", "e4d5"))
        )
        assert verdict.classification is C.BEST


class TestMissedOpportunity:
    def test_not_punishing_a_blunder(self) -> None:
        verdict = classify(inp(START, "d2d4", ev(("e2e4", 500), ("d2d4", 0)), previous=C.BLUNDER))
        assert verdict.classification is C.MISS

    def test_needs_a_decisive_best_move(self) -> None:
        verdict = classify(
            inp(START, "d2d4", ev(("e2e4", 150), ("d2d4", -50)), previous=C.BLUNDER)  # Δ 18.2
        )
        assert verdict.classification is C.MISTAKE

    def test_needs_an_opponent_error(self) -> None:
        verdict = classify(
            inp(START, "d2d4", ev(("e2e4", 500), ("d2d4", 0)), previous=C.INACCURACY)
        )
        assert verdict.classification is C.BLUNDER


# White knight to f5, where the g6 pawn can take it.
KNIGHT_SAC = "6k1/5p1p/6p1/8/3N4/8/5PPP/6K1 w - - 0 1"


class TestBrilliant:
    def test_piece_left_en_prise_while_best(self) -> None:
        verdict = classify(inp(KNIGHT_SAC, "d4f5", ev(("d4f5 g6f5", 50), ("d4e2", 40))))
        assert verdict.classification is C.BRILLIANT

    def test_not_when_already_totally_winning(self) -> None:
        verdict = classify(inp(KNIGHT_SAC, "d4f5", ev(("d4f5", 800), ("d4e2", 790))))
        assert verdict.classification is C.BEST

    def test_not_when_the_result_is_bad(self) -> None:
        verdict = classify(inp(KNIGHT_SAC, "d4f5", ev(("d4f5", -30), ("d4e2", -40))))
        assert verdict.classification is C.BEST

    def test_not_when_it_loses_win_percentage(self) -> None:
        verdict = classify(inp(KNIGHT_SAC, "d4f5", ev(("d4e2", 50), ("d4f5", 0))))
        assert verdict.classification is C.GOOD

    def test_quiet_move_is_not_a_sacrifice(self) -> None:
        move = inp(KNIGHT_SAC, "d4e2", ev(("d4e2", 50), ("d4f5", 40)))
        assert not is_sacrifice(move, THRESHOLDS)


def test_material_drop_follows_the_exchange_past_the_horizon() -> None:
    board = chess.Board("3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1")
    # Qxd5 Rxd5: +1 then -9. With horizon 1 the recapture is still counted.
    assert _material_drop(board, ("d1d5", "d8d5"), horizon=1) == 8
    assert _material_drop(board, ("d1d5", "d8d5", "e1e2"), horizon=6) == 8


def test_obvious_recapture_detection() -> None:
    board = chess.Board()
    for uci in ["e2e4", "d7d5", "e4d5"]:
        board.push_uci(uci)
    assert is_obvious_recapture(board, chess.Move.from_uci("d8d5"))
    assert not is_obvious_recapture(board, chess.Move.from_uci("g8f6"))
    assert not is_obvious_recapture(chess.Board(), chess.Move.from_uci("e2e4"))


def test_mate_scores() -> None:
    verdict = classify(inp(START, "e2e4", mate_ev("e2e4", 3)))
    assert verdict.win_before == 100.0 and verdict.delta == 0.0
