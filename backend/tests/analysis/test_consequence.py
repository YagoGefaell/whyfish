"""Consequence point of a line (SPEC §5.3). Fixed positions, no engine."""

import chess

from app.analysis.consequence import Consequence, consequence


def cons(fen: str, line: str, history: str = "") -> Consequence:
    board = chess.Board(fen)
    for san in history.split():
        board.push_san(san)
    return consequence(board, tuple(line.split()))


# White plays a3?: Ne2+ Kh1 Nxc3 bxc3 -- the queen goes three plies after the check.
QUEEN_LOST_LATER = "6k1/5ppp/8/8/5n2/2Q5/PP3PPP/6K1 w - - 0 1"


def test_queen_lost_later_includes_the_recapture() -> None:
    c = cons(QUEEN_LOST_LATER, "a2a3 f4e2 g1h1 e2c3 b2c3 g8f8")
    assert c.kind == "material" and c.settled
    assert c.ply == 4  # the recapture bxc3, not the capture Nxc3
    assert (c.lost, c.won, c.material) == (("queen",), ("knight",), -6)


def test_line_cut_in_the_middle_of_an_exchange_is_resolved() -> None:
    # The line stops right after Nxc3: bxc3 is still pending.
    c = cons(QUEEN_LOST_LATER, "a2a3 f4e2 g1h1 e2c3")
    assert c.kind == "material" and not c.settled and c.ply is None
    assert c.material == -6


def test_mate() -> None:
    c = cons(chess.STARTING_FEN, "g2g4 d8h4", history="f3 e5")
    assert c.kind == "mate" and c.ply == 1 and c.mover_mated


def test_even_trade_is_no_consequence() -> None:
    c = cons("4k3/4bq2/8/6B1/8/8/8/4K2Q w - - 0 1", "g5e7 f7e7 h1h5")
    assert c.kind == "none" and c.ply is None


def test_material_lost_and_won_back_is_no_consequence() -> None:
    # Black takes a pawn, white takes one back later.
    c = cons("4k3/p7/8/8/8/1r6/1P6/R3K3 w - - 0 1", "e1f1 b3b2 a1a7 b2b1 f1e2")
    assert c.kind == "none"


def test_the_point_is_where_the_material_settles() -> None:
    # Qxd5? Rxd5 Rxd5: queen for rook and pawn; the point is the recapture, not the king move.
    c = cons("3rk3/8/8/3p4/8/8/8/3RK2Q w - - 0 1", "h1d5 d8d5 d1d5 e8e7")
    assert c.kind == "material" and c.ply == 2 and c.material == -3
    assert (c.lost, c.won) == (("queen",), ("rook", "pawn"))


def test_promotion() -> None:
    c = cons("8/P6k/8/8/8/8/8/K7 w - - 0 1", "a7a8q h7g6")
    assert c.kind == "material" and c.ply == 0 and c.promoted == ("queen",) and c.material == 8


def test_later_small_trades_do_not_move_the_point() -> None:
    from app.analysis.consequence import _point

    # 21...dxc3?? (+3) Rxd8 (-6, recapture pending) Raxd8 (-1): the queen for rook and knight.
    # gxh6 (-2) and then pawns come and go (-2, -3, -2): a two-pawn swing needs the exact
    # balance, so the story ends at gxh6, not at the last pawn of the line.
    values = [3, -6, -1, -2, -2, -3, -2, -2]
    quiet = [True, False, True, True, True, True, True, True]
    assert _point(values, quiet, start=0, final=-2) == 3
    # With a piece-sized swing a pawn of tolerance: the knight is lost at ply 1.
    assert _point([0, -3, -2, -3, -4], [True, True, True, True, True], start=0, final=-4) == 1
    # A one-pawn swing needs the exact balance, and is not reached at the start.
    assert _point([0, -1, -1], [True, True, True], start=0, final=-1) == 1
    # The loss is won back later (more than a pawn): the point moves on.
    assert _point([-3, 0, -3], [True, True, True], start=0, final=-3) == 2
