import chess
import pytest

from app.play.pgn import PgnImportError, detect_user_color, parse_pgn, pgn_result
from app.play.rules import PlayerColor

OPERA = """[Event "Paris Opera"]
[White "Paul Morphy"]
[Black "Duke Karl"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 (2... Nc6 3. Bb5) 3. d4 {a comment} Bg4 1-0
"""


def test_main_line_only() -> None:
    parsed = parse_pgn(OPERA)
    assert parsed.ucis == ["e2e4", "e7e5", "g1f3", "d7d6", "d2d4", "c8g4"]
    assert (parsed.white, parsed.black) == ("Paul Morphy", "Duke Karl")
    assert parsed.games_in_text == 1


def test_counts_games_and_keeps_the_first() -> None:
    parsed = parse_pgn(OPERA + "\n\n" + OPERA.replace("Paul Morphy", "Someone"))
    assert parsed.games_in_text == 2
    assert parsed.white == "Paul Morphy"


def test_custom_start_position() -> None:
    pgn = '[SetUp "1"]\n[FEN "8/P6k/8/8/8/8/8/K7 w - - 0 1"]\n\n1. a8=Q *'
    parsed = parse_pgn(pgn)
    assert parsed.initial_fen == "8/P6k/8/8/8/8/8/K7 w - - 0 1"
    assert parsed.ucis == ["a7a8q"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "vacío"),
        ("   \n", "vacío"),
        ('[White "a"]\n\n*', "no contiene jugadas"),
        ("1. e4 e5 2. Ke3 *", "no válidas"),
    ],
)
def test_errors(text: str, message: str) -> None:
    with pytest.raises(PgnImportError, match=message):
        parse_pgn(text)


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("paul morphy", PlayerColor.WHITE),
        ("  Duke Karl ", PlayerColor.BLACK),
        ("Jugador", None),
    ],
)
def test_detect_user_color(player: str, expected: PlayerColor | None) -> None:
    assert detect_user_color(parse_pgn(OPERA), player) is expected


def test_detect_is_ambiguous_with_the_same_name_on_both_sides() -> None:
    parsed = parse_pgn('[White "Yo"]\n[Black "yo"]\n\n1. e4 *')
    assert detect_user_color(parsed, "yo") is None


def test_unknown_header_values_are_none() -> None:
    parsed = parse_pgn('[Event "?"]\n[Date "????.??.??"]\n[White "?"]\n[Black ""]\n\n1. e4 *')
    assert (parsed.white, parsed.black, parsed.event, parsed.date) == (None, None, None, None)
    assert parse_pgn('[Date "1858.??.??"]\n\n1. e4 *').date == "1858.??.??"


def test_result_from_header_or_final_position() -> None:
    parsed = parse_pgn("1. f3 e5 2. g4 Qh4# *")
    board = chess.Board()
    for uci in parsed.ucis:
        board.push_uci(uci)
    assert pgn_result(parsed, board) == "0-1"
    assert pgn_result(parse_pgn(OPERA), chess.Board()) == "1-0"
    assert pgn_result(parse_pgn("1. e4 *"), chess.Board()) == "*"
