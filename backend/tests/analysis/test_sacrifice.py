"""Sacrifice detection with resolved material (SPEC §3.1.2). No engine."""

import chess

from app.analysis import material
from app.analysis.sacrifice import Sacrifice, find_sacrifice
from app.analysis.types import EngineLine, PositionEval


def lines(*specs: tuple[str, int]) -> PositionEval:
    """(space-separated UCI moves, cp from the side to move's point of view)."""
    return PositionEval(lines=tuple(EngineLine(tuple(m.split()), cp=cp) for m, cp in specs))


NO_LINES = PositionEval(lines=())


def sac(
    fen: str, move: str, before: PositionEval, after: PositionEval = NO_LINES
) -> Sacrifice | None:
    return find_sacrifice(chess.Board(fen), chess.Move.from_uci(move), before, after)


KNIGHT_SAC = "6k1/5p1p/6p1/8/3N4/8/5PPP/6K1 w - - 0 1"


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
    def test_piece_left_en_prise_and_taken_in_the_engine_line(self) -> None:
        result = sac(KNIGHT_SAC, "d4f5", lines(("d4f5 g6f5", -20), ("d4e2", -40)))
        assert result is not None
        assert (result.square, result.amount, result.line_end) == ("f5", 3, -3)
        assert result.line[:2] == ("d4f5", "g6f5")

    def test_capture_found_in_the_opponents_multipv(self) -> None:
        # The engine's best reply declines; the capture is the opponent's 2nd line (-10 for
        # them = +10 for us, still fine).
        before = lines(("d4f5 g8h8", 50), ("d4e2", 40))
        after = lines(("g8h8", -50), ("g6f5", -10))
        result = sac(KNIGHT_SAC, "d4f5", before, after)
        assert result is not None and result.line[:2] == ("d4f5", "g6f5")

    def test_not_verified_if_no_line_shows_the_capture(self) -> None:
        before = lines(("d4f5 g8h8", 50), ("d4e2", 40))
        assert sac(KNIGHT_SAC, "d4f5", before, lines(("g8h8", -50))) is None

    def test_not_if_taking_is_good_for_the_opponent(self) -> None:
        before = lines(("d4e2", 40), ("d4f5 g8h8", 0))
        assert sac(KNIGHT_SAC, "d4f5", before, lines(("g6f5", 300))) is None

    def test_material_recovered_at_the_end_of_the_line(self) -> None:
        # Nf5 gxf5 uncovers the d-file: Qd8+ and Qxa5 wins the rook back.
        fen = "6k1/5p1p/6p1/r7/3N4/8/5PPP/3Q2K1 w - - 0 1"
        before = lines(("d4f5 g6f5 d1d8 g8g7 d8a5", 100))
        # ...Rxf5 is also legal: not in the opponent's MultiPV, bounded by its last line.
        after = lines(("g6f5 d1d8 g8g7 d8a5", -100), ("a5a1", -150))
        result = sac(fen, "d4f5", before, after)
        assert result is not None and result.line_end == 2 and not result.bound

    def test_unchecked_capture_is_not_a_sacrifice(self) -> None:
        # Same position without opponent lines: ...Rxf5 cannot be checked.
        fen = "6k1/5p1p/6p1/r7/3N4/8/5PPP/3Q2K1 w - - 0 1"
        assert sac(fen, "d4f5", lines(("d4f5 g6f5 d1d8 g8g7 d8a5", 100))) is None

    def test_capture_outside_the_multipv_is_bounded(self) -> None:
        # Like 24.Rxd4 (Kasparov): the opponent declines and taking is not even in its lines.
        before = lines(("d4f5 g8h8", 50))
        after = lines(("g8h8", -50), ("h7h5", -60), ("f7f6", -80))
        result = sac(KNIGHT_SAC, "d4f5", before, after)
        assert result is not None and result.bound and result.line == ("d4f5", "g6f5")

    def test_forced_loss_in_check_is_not_a_sacrifice(self) -> None:
        # 8.Bd2 (in check): no legal move saves the g6 bishop.
        fen = "rn1qk2r/ppp2ppp/4p1B1/3n4/1b1P4/4PN2/PP3PPP/RNBQK2R w KQkq - 1 8"
        assert sac(fen, "c1d2", lines(("c1d2 h7g6 d2b4 d5b4", 128))) is None

    def test_piece_attacked_only_by_the_king_and_defended(self) -> None:
        # 21.Nd6 (user game, evaluations as stored): only Ke7 attacks d6 and Rd1 defends it.
        fen = "r2n4/pp1nkpp1/4p1p1/1N4N1/8/P3P3/1P2KPPP/3R4 w - - 2 21"
        before = lines(("f2f4 f7f6 g5f3 d8c6 b5d6", 20), ("d1c1 f7f6", 16), ("g5f3 d8c6", 12))
        after = lines(("d7b6 g5f3 f7f6 f3h4 b6d5", -5))
        assert sac(fen, "b5d6", before, after) is None

    def test_trapped_piece_lost_anyway(self) -> None:
        # Bishop a7 attacked by Ra8 and no square to go: losing it is not a sacrifice.
        fen = "r3k3/B1p5/1p6/8/8/8/8/4K3 w - - 0 1"
        assert sac(fen, "e1d2", lines(("e1d2 a8a7", -300))) is None
