"""Platform responses -> OnlineGame (pure)."""

from datetime import UTC, datetime

from app.sync import chesscom, lichess
from tests.sync.fakes import chesscom_game, lichess_game

WHEN = datetime(2026, 10, 1, 12, 30, 0, tzinfo=UTC)


def test_lichess_game() -> None:
    game = lichess.parse_game(lichess_game("abc", WHEN, speed="ultraBullet"), "https://lichess.org")
    assert game is not None
    assert (game.platform, game.external_id, game.url) == (
        "lichess",
        "abc",
        "https://lichess.org/abc",
    )
    assert game.played_at == WHEN and game.time_class == "bullet"
    assert (game.time_control, game.white_elo, game.black_elo) == ("180+2", 1500, 1600)


def test_lichess_variants_and_ai_games_are_skipped() -> None:
    assert lichess.parse_game(lichess_game("x", WHEN, variant="chess960"), "") is None
    ai = lichess_game("y", WHEN)
    ai["players"]["black"] = {"aiLevel": 3}
    assert lichess.parse_game(ai, "") is None
    assert lichess.parse_game(lichess_game("z", WHEN, variant="fromPosition"), "") is not None


def test_chesscom_game() -> None:
    game = chesscom.parse_game(chesscom_game("u1", WHEN, time_class="daily"))
    assert game is not None
    assert game.platform == "chesscom" and game.external_id == "u1"
    assert game.played_at == WHEN  # from UTCDate / UTCTime, not the end time
    assert game.time_class == "correspondence"


def test_chesscom_variants_are_skipped() -> None:
    assert chesscom.parse_game(chesscom_game("u2", WHEN, rules="chess960")) is None
