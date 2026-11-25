import chess

from app.analysis.book import build_book, default_book


def board_after(*sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


def test_named_line_and_its_prefixes_are_book() -> None:
    book = build_book([("B20", "Sicilian Defense", "1. e4 c5"), ("C20", "King's Pawn", "1. e4 e5")])
    assert book.lookup(board_after("e4", "c5")) is not None
    assert book.contains(board_after("e4"))
    assert not book.contains(board_after("d4"))


def test_most_specific_name_wins() -> None:
    book = build_book(
        [
            ("B20", "Sicilian Defense", "1. e4 c5"),
            ("B27", "Sicilian Defense: Long Line", "1. e4 c5 2. Nf3 g6"),
        ]
    )
    found = book.lookup(board_after("e4", "c5"))
    assert found is not None and found.name == "Sicilian Defense"


def test_real_dataset_and_transpositions() -> None:
    book = default_book()
    sicilian = book.lookup(board_after("e4", "c5", "Nf3"))
    transposed = book.lookup(board_after("Nf3", "c5", "e4"))
    assert sicilian is not None and sicilian.name.startswith("Sicilian")
    assert transposed == sicilian
    assert not book.contains(board_after("e4", "e5", "Ke2", "Ke7", "Ke3", "Ke6"))
