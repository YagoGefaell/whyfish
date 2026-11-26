import chess

from app.analysis.detectors.structure import (
    PawnChange,
    develops,
    passed_pawns,
    pawn_changes,
    phase,
    weakens_king,
)


def test_phases() -> None:
    assert phase(chess.Board()) == "opening"
    middle = chess.Board()
    middle.fullmove_number = 20
    assert phase(middle) == "middlegame"
    assert phase(chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 40")) == "endgame"


def test_doubled_and_isolated_after_bxc6() -> None:
    # 1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6, black recaptures with the b-pawn.
    board = chess.Board("r1bqkbnr/1ppp1ppp/p1B5/4p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 4")
    changes = pawn_changes(board, chess.Move.from_uci("b7c6"))
    assert PawnChange("doubled", "black", "c") in changes
    assert PawnChange("isolated", "black", "a") in changes


def test_passed_pawn_created_by_a_capture() -> None:
    board = chess.Board("4k3/8/8/2p5/1P6/8/8/4K3 w - - 0 1")
    changes = pawn_changes(board, chess.Move.from_uci("b4c5"))
    assert PawnChange("passed", "white", "c5") in changes


def test_an_advancing_passed_pawn_is_not_new() -> None:
    board = chess.Board("4k3/8/8/2P5/8/8/8/4K3 w - - 0 1")
    assert chess.C5 in passed_pawns(board, chess.WHITE)
    assert pawn_changes(board, chess.Move.from_uci("c5c6")) == ()


def test_shield_pawn_moves() -> None:
    castled = chess.Board("r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7")
    assert weakens_king(castled, chess.Move.from_uci("g2g4"))
    assert weakens_king(castled, chess.Move.from_uci("h2h3"))
    assert not weakens_king(castled, chess.Move.from_uci("a2a3"))
    assert not weakens_king(chess.Board(), chess.Move.from_uci("g2g4"))  # king not castled


def test_development() -> None:
    assert develops(chess.Board(), chess.Move.from_uci("g1f3"))
    assert not develops(chess.Board(), chess.Move.from_uci("e2e4"))
