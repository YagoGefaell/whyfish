import chess

from app.analysis.detectors.common import PieceOn
from app.analysis.detectors.lines import line_outcome

HANGING_KNIGHT = "4k3/8/8/3n4/8/8/8/3QK3 w - - 0 1"


def test_winning_a_piece() -> None:
    out = line_outcome("best", chess.Board(HANGING_KNIGHT), ("d1d5",), 900, None, 10)
    assert out.material == 3
    assert out.sans == ("Qxd5",)
    assert out.captures[0].captured == PieceOn("knight", "black", "d5")
    assert out.base_ply == 10


def test_settles_a_pending_capture_with_see() -> None:
    # The line is empty but white can take the knight: it counts.
    out = line_outcome("best", chess.Board(HANGING_KNIGHT), (), 900, None, 0)
    assert out.material == 3


def test_settles_for_the_opponent_too() -> None:
    # White plays a waiting move and leaves the queen en prise to the rook.
    board = chess.Board("3rk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    out = line_outcome("played", board, ("e1f2",), -900, None, 0)
    assert out.material == -9


def test_stops_at_illegal_moves_and_keeps_the_score() -> None:
    out = line_outcome("best", chess.Board(HANGING_KNIGHT), ("d1d5", "a1a2"), None, 3, 0)
    assert out.ucis == ("d1d5",)
    assert out.mate == 3
    assert out.win == 100.0


def test_promotion_index() -> None:
    board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    out = line_outcome("best", board, ("a7a8q",), 1000, None, 0)
    assert out.promotion == 0
    assert out.material == 8  # a pawn becomes a queen
