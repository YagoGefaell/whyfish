"""Sacrifice detection with resolved material (SPEC §3.1.2). No engine."""

import chess

from app.analysis import material
from app.analysis.sacrifice import Sacrifice, find_sacrifice


def sac(fen: str, line: str) -> Sacrifice | None:
    board = chess.Board(fen)
    ucis = tuple(line.split())
    return find_sacrifice(board, chess.Move.from_uci(ucis[0]), ucis)


class TestResolvedBalance:
    def test_pending_recapture_is_resolved(self) -> None:
        # White has just taken a bishop on g6 and black recaptures with the h-pawn.
        board = chess.Board("rn1qkb1r/ppp2ppp/4p1B1/3n4/3P4/4PN2/PP3PPP/RNBQK2R b KQkq - 0 7")
        assert material.balance(board, chess.WHITE) == 3
        assert material.resolved_balance(board, chess.WHITE, 8) == 0

    def test_in_check_every_evasion_is_searched(self) -> None:
        board = chess.Board("rn1qk2r/ppp2ppp/4p1B1/3n4/1b1P4/4PN2/PP3PPP/RNBQK2R w KQkq - 1 8")
        assert material.balance(board, chess.WHITE) == 3
        assert material.resolved_balance(board, chess.WHITE, 8) == 0

    def test_stand_pat_when_captures_lose(self) -> None:
        board = chess.Board("4k3/8/2p5/3n4/8/8/8/3RK3 w - - 0 1")  # Rxd5 cxd5 loses the exchange
        assert material.resolved_balance(board, chess.WHITE, 8) == material.balance(
            board, chess.WHITE
        )


class TestFindSacrifice:
    def test_piece_left_en_prise(self) -> None:
        result = sac("6k1/5p1p/6p1/8/3N4/8/5PPP/6K1 w - - 0 1", "d4f5 g6f5")
        assert result is not None
        assert result.amount == 3 and result.line_end == -3

    def test_exchange_followed_past_the_horizon(self) -> None:
        # Qxd5 Rxd5: queen for a pawn.
        result = sac("3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1", "d1d5 d8d5")
        assert result is not None and result.amount == 8

    def test_material_recovered_at_the_end_of_the_line(self) -> None:
        # Nf5 gxf5 uncovers the d-file: Qd8+ and Qxa5 wins the rook back (line_end > 0).
        board = "6k1/5p1p/6p1/r7/3N4/8/5PPP/3Q2K1 w - - 0 1"
        result = sac(board, "d4f5 g6f5 d1d8 g8g7 d8a5")
        assert result is not None
        assert result.amount == 3 and result.line_end == 2

    def test_forced_loss_in_check_is_not_a_sacrifice(self) -> None:
        # 8.Bd2 (in check): no legal move saves the g6 bishop.
        fen = "rn1qk2r/ppp2ppp/4p1B1/3n4/1b1P4/4PN2/PP3PPP/RNBQK2R w KQkq - 1 8"
        assert sac(fen, "c1d2 h7g6 d2b4 d5b4 d1b3 c7c5") is None

    def test_line_ending_in_the_middle_of_an_exchange(self) -> None:
        # Bishop trade: Bxe7 Qxe7 is even, even if the line stops right after Bxe7.
        board = "4k3/4bq2/8/6B1/8/8/8/4K3 w - - 0 1"
        assert sac(board, "g5e7") is None

    def test_trapped_piece_lost_anyway(self) -> None:
        # Bishop a7 attacked by Ra8 and no square to go: losing it is not a sacrifice.
        assert sac("r3k3/B1p5/1p6/8/8/8/8/4K3 w - - 0 1", "e1d2 a8a7") is None
