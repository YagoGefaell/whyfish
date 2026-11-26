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


class TestLeftEnPrise:
    def test_moving_piece_into_pawn_attack(self) -> None:
        board = chess.Board("4k3/8/2p5/8/8/2N5/8/4K3 w - - 0 1")
        hanging = material.left_en_prise(board, chess.Move.from_uci("c3b5"), 2)
        assert [sq for sq, _ in hanging] == [chess.B5]

    def test_even_trade_is_not_a_sacrifice(self) -> None:
        board = chess.Board("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
        assert material.left_en_prise(board, chess.Move.from_uci("d1d8"), 2) == []

    def test_unmoved_queen_left_en_prise(self) -> None:
        # The bishop on e2 blocks the rook's attack on the queen; moving it exposes the queen.
        board = chess.Board("4r1k1/8/8/8/8/8/4B3/4Q1K1 w - - 0 1")
        hanging = material.left_en_prise(board, chess.Move.from_uci("e2b5"), 2)
        assert hanging == [(chess.E1, 9)]  # Rxe1+ wins the queen for nothing

    def test_piece_already_attacked_and_left_counts_if_it_could_be_saved(self) -> None:
        # The knight on d5 is attacked by the c6 pawn; white plays a king move instead of saving it.
        board = chess.Board("4k3/8/2p5/3N4/8/8/8/4K3 w - - 0 1")
        hanging = material.left_en_prise(board, chess.Move.from_uci("e1d2"), 2)
        assert [sq for sq, _ in hanging] == [chess.D5]

    def test_trapped_piece_that_is_lost_anyway_does_not_count(self) -> None:
        # Bishop a7 attacked by Ra8: Bb8 is covered by the rook and Bxb6 cxb6 still loses it.
        board = chess.Board("r3k3/B1p5/1p6/8/8/8/8/4K3 w - - 0 1")
        assert material.see(_flip(board), chess.A7) == 3  # en prise before the move
        assert material.left_en_prise(board, chess.Move.from_uci("e1d2"), 2) == []

    def test_piece_lost_anyway_while_in_check_does_not_count(self) -> None:
        # 7...Bb4+: no check evasion also saves the g6 bishop (it was en prise before).
        board = chess.Board("rn1qk2r/ppp2ppp/4p1B1/3n4/1b1P4/4PN2/PP3PPP/RNBQK2R w KQkq - 1 8")
        assert material.left_en_prise(board, chess.Move.from_uci("c1d2"), 2) == []


def _flip(board: chess.Board) -> chess.Board:
    flipped = board.copy(stack=False)
    flipped.push(chess.Move.null())
    return flipped
