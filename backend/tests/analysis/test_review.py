import chess
import pytest

from app.analysis.book import build_book
from app.analysis.review import MoveReview, build_review, key_moments
from app.analysis.types import Classification as C
from app.analysis.types import EngineLine, PositionEval


def mr(ply: int, cls: C, delta: float) -> MoveReview:
    color = chess.WHITE if ply % 2 == 0 else chess.BLACK
    return MoveReview(ply, color, "e2e4", "e4", cls, 50, 50 - delta, delta, 0, None, None, (), ())


class TestKeyMoments:
    def test_only_the_users_moves(self) -> None:
        moves = [mr(0, C.BLUNDER, 30), mr(1, C.BLUNDER, 40)]
        assert key_moments(moves, chess.WHITE) == [0]
        assert key_moments(moves, chess.BLACK) == [1]

    def test_errors_by_delta_then_great_moves_returned_in_game_order(self) -> None:
        moves = [
            mr(0, C.INACCURACY, 6),
            mr(2, C.GREAT, 0),
            mr(4, C.BLUNDER, 30),
            mr(6, C.MISS, 12),
            mr(8, C.MISTAKE, 15),
            mr(10, C.BRILLIANT, 0),
            mr(12, C.INACCURACY, 7),
            mr(14, C.BEST, 0),
        ]
        # Top 5: errors 4 (30), 8 (15), 6 (12), 12 (7), 0 (6); no room for ! / !!.
        assert key_moments(moves, chess.WHITE) == [0, 4, 6, 8, 12]

    def test_highlights_fill_the_gaps_brilliant_first(self) -> None:
        moves = [mr(0, C.GREAT, 0), mr(2, C.MISTAKE, 15), mr(4, C.BRILLIANT, 0)]
        assert key_moments(moves, chess.WHITE) == [0, 2, 4]

    def test_small_deltas_are_ignored(self) -> None:
        # A missed opportunity always has Δ >= 10, but guard the threshold anyway.
        assert key_moments([mr(0, C.INACCURACY, 4.9)], chess.WHITE) == []


def lines(*items: tuple[str, int]) -> PositionEval:
    return PositionEval(lines=tuple(EngineLine(tuple(m.split()), cp=cp) for m, cp in items))


def test_build_review() -> None:
    book = build_book([("C20", "King's Pawn Game", "1. e4 e5")])
    evals = [
        lines(("e2e4 e7e5", 30), ("d2d4", 25)),
        lines(("e7e5", -30), ("c7c5", -35)),  # black to move: -30 for black
        lines(("g1f3", 30)),
        PositionEval(terminal_win=0.0),  # not reached in a real game; just a value
    ]
    review = build_review(chess.STARTING_FEN, ["e2e4", "e7e5", "a2a3"], evals, chess.WHITE, book)
    assert [m.classification for m in review.moves][:2] == [C.BOOK, C.BOOK]
    assert review.opening is not None and review.opening.name == "King's Pawn Game"
    assert review.moves[0].best_line == ("e4", "e5")
    assert review.moves[1].color == chess.BLACK
    # White-POV evals: black to move at -30 means white +30.
    assert [e.cp for e in review.evals[:3]] == [30, 30, 30]
    assert review.evals[3].win == 100.0  # black (to move) is "mated" -> white 100
    assert review.white.counts[C.BOOK] == 1 and review.black.counts[C.BOOK] == 1
    assert review.white.accuracy is not None


def test_build_review_needs_one_eval_per_position() -> None:
    with pytest.raises(ValueError, match="one evaluation per position"):
        build_review(chess.STARTING_FEN, ["e2e4"], [lines(("e2e4", 0))], chess.WHITE, None)
