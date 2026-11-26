import chess

from app.analysis.detectors.common import PieceOn
from app.analysis.detectors.threats import (
    capture_threats,
    hanging_after,
    mate_threat,
    new_threats,
    parried_threats,
)

# 1. e4 e5 2. Nf3, black to move: the e5 pawn is attacked and undefended.
AFTER_NF3 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
# 1. e4 e5 2. Qh5 Nc6 3. Bc4, black to move: Qxf7 is mate.
SCHOLAR = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"


def test_queen_left_hanging() -> None:
    board = chess.Board(AFTER_NF3)
    hanging = hanging_after(board, chess.Move.from_uci("d8g5"), 1)
    assert hanging[0].piece == PieceOn("queen", "black", "g5")
    assert hanging[0].loss == 9
    assert hanging[0].attackers == ("f3",)


def test_defended_piece_is_not_hanging() -> None:
    board = chess.Board(AFTER_NF3)
    assert hanging_after(board, chess.Move.from_uci("b8c6"), 1) == ()


def test_capture_threats_if_the_other_side_passed() -> None:
    board = chess.Board(AFTER_NF3)  # black to move; white's threats as if black passed
    threats = capture_threats(board, chess.WHITE, 1)
    assert [(t.target.square, t.gain, t.move) for t in threats] == [("e5", 1, "f3e5")]


def test_new_threat_of_a_developing_move() -> None:
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    threats = new_threats(board, chess.Move.from_uci("g1f3"), 1)
    assert [t.target.square for t in threats] == ["e5"]


def test_new_mate_threat() -> None:
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3")
    threats = new_threats(board, chess.Move.from_uci("f1c4"), 1)
    assert threats[0].kind == "mate"
    assert threats[0].move == "h5f7"


def test_mate_threat_lookup() -> None:
    mate = mate_threat(chess.Board(SCHOLAR), chess.WHITE)
    assert mate is not None and mate.move == "h5f7" and mate.target.square == "e8"


def test_parried_by_defending() -> None:
    board = chess.Board(AFTER_NF3)
    parried = parried_threats(board, chess.Move.from_uci("b8c6"), 1)
    assert [(p.threat.target.square, p.how) for p in parried] == [("e5", "defended")]


def test_mate_threat_stopped() -> None:
    parried = parried_threats(chess.Board(SCHOLAR), chess.Move.from_uci("g7g6"), 1)
    assert parried[0].how == "mate_stopped"


def test_mate_threat_ignored() -> None:
    parried = parried_threats(chess.Board(SCHOLAR), chess.Move.from_uci("g8f6"), 1)
    assert all(p.how != "mate_stopped" for p in parried)


def test_parried_by_moving_the_piece() -> None:
    # The white knight on c3 is attacked by the pawn on b4.
    board = chess.Board("4k3/8/8/8/1p6/2N5/8/4K3 w - - 0 1")
    parried = parried_threats(board, chess.Move.from_uci("c3d5"), 1)
    assert [(p.how, p.piece_after) for p in parried] == [
        ("moved", PieceOn("knight", "white", "d5"))
    ]


def test_no_parried_threats_when_in_check() -> None:
    board = chess.Board("4k3/8/8/8/1p6/2N5/8/r3K3 w - - 0 1")
    assert parried_threats(board, chess.Move.from_uci("e1e2"), 1) == ()
