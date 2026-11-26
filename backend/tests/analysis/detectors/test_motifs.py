import chess

from app.analysis.detectors.common import PieceOn
from app.analysis.detectors.motifs import motifs_in_line, motifs_of_move


def kinds(fen: str, uci: str) -> dict[str, tuple[str, ...]]:
    motifs = motifs_of_move(chess.Board(fen), chess.Move.from_uci(uci))
    return {m.kind: tuple(t.square for t in m.targets) for m in motifs}


def test_knight_fork_king_and_rook() -> None:
    assert kinds("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "b5c7") == {"fork": ("e8", "a8")}


def test_no_fork_against_defended_cheaper_pieces() -> None:
    # The knight attacks two pawns: not a fork worth mentioning.
    assert kinds("4k3/8/2p1p3/8/3N4/8/8/4K3 w - - 0 1", "d4b5") == {}


def test_fork_of_undefended_pieces_by_a_queen() -> None:
    found = kinds("4k3/8/8/1b4n1/8/8/8/3QK3 w - - 0 1", "d1d5")
    assert set(found["fork"]) == {"b5", "g5"}


def test_absolute_pin() -> None:
    motifs = motifs_of_move(
        chess.Board("4k3/8/2n5/8/8/8/8/4KB2 w - - 0 1"), chess.Move.from_uci("f1b5")
    )
    pin = next(m for m in motifs if m.kind == "pin")
    assert pin.by == PieceOn("bishop", "white", "b5")
    assert pin.targets == (PieceOn("knight", "black", "c6"), PieceOn("king", "black", "e8"))


def test_discovered_attack_on_the_queen() -> None:
    found = kinds("4k3/4q3/8/8/4N3/8/8/4R1K1 w - - 0 1", "e4c5")
    assert found["discovered_attack"] == ("e7",)


def test_double_check() -> None:
    found = kinds("4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1", "e4f6")
    assert found["double_check"] == ("e8",)


def test_motifs_in_line_are_indexed() -> None:
    board = chess.Board("r3k3/7p/8/1N6/8/8/8/4K3 b - - 0 1")
    motifs = motifs_in_line(board, ("h7h6", "b5c7"), plies=4)
    assert [(m.kind, m.index) for m in motifs] == [("fork", 1)]
    assert motifs_in_line(board, ("h7h6", "b5c7"), plies=1) == ()
