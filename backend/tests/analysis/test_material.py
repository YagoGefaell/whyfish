import chess

from app.analysis import material


def test_balance() -> None:
    board = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    assert material.balance(board, chess.WHITE) == 5
    assert material.balance(board, chess.BLACK) == -5


class TestSee:
    def test_undefended_piece(self) -> None:
        board = chess.Board("4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1")
        assert material.see(board, chess.D5) == 3

    def test_defended_piece_is_not_worth_taking_with_a_rook(self) -> None:
        board = chess.Board("4k3/8/2p5/3n4/8/8/8/3RK3 w - - 0 1")
        assert material.see(board, chess.D5) == 0  # Rxd5 cxd5 loses the exchange

    def test_pawn_takes_defended_knight(self) -> None:
        board = chess.Board("4k3/8/2p5/3n4/4P3/8/8/4K3 w - - 0 1")
        assert material.see(board, chess.D5) == 2  # exd5 cxd5: knight for pawn

    def test_pinned_attacker_cannot_capture(self) -> None:
        board = chess.Board("4k3/4r3/8/8/3n4/4B3/8/4K3 w - - 0 1")  # Be3 pinned by Re7
        assert material.see(board, chess.D4) == 0

    def test_xray_recapture(self) -> None:
        # Rooks doubled on the d-file vs a knight defended once by a rook.
        board = chess.Board("3rk3/8/8/3n4/8/8/3R4/3RK3 w - - 0 1")
        assert material.see(board, chess.D5) == 3


class TestNewlyEnPrise:
    def test_moving_piece_into_pawn_attack(self) -> None:
        board = chess.Board("4k3/8/2p5/8/8/2N5/8/4K3 w - - 0 1")
        hanging = material.newly_en_prise(board, chess.Move.from_uci("c3b5"), 2)
        assert [sq for sq, _ in hanging] == [chess.B5]

    def test_even_trade_is_not_a_sacrifice(self) -> None:
        board = chess.Board("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
        assert material.newly_en_prise(board, chess.Move.from_uci("d1d8"), 2) == []

    def test_unmoved_queen_left_en_prise(self) -> None:
        # The bishop on e2 blocks the rook's attack on the queen; moving it exposes the queen.
        board = chess.Board("4r1k1/8/8/8/8/8/4B3/4Q1K1 w - - 0 1")
        hanging = material.newly_en_prise(board, chess.Move.from_uci("e2b5"), 2)
        assert hanging == [(chess.E1, 9)]  # Rxe1+ wins the queen for nothing
