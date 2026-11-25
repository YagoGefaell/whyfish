"""Acceptance (phase 2): analyse a 40-move game with the default settings in < 60 s,
end to end through the API with the real Stockfish, and get a full review."""

import time

import chess
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import BotLevel, Settings
from app.main import create_app
from app.models.game import Game, Move
from app.play.rules import PlayerColor, game_outcome
from tests.analysis.real_fixtures import load_game

_settings = Settings(database_url="sqlite://")  # defaults for everything analysis-related

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        _settings.stockfish_path is None or not _settings.stockfish_path.is_file(),
        reason="STOCKFISH_PATH not set or binary missing",
    ),
]

MAX_SECONDS = 60


def insert_game(client: TestClient, pgn: str, player: PlayerColor) -> int:
    initial_fen, ucis = load_game(pgn)
    board = chess.Board(initial_fen)
    with Session(client.app.state.db_engine) as session:  # type: ignore[attr-defined]
        game = Game(player_color=player, bot_level=BotLevel.MAX, initial_fen=initial_fen)
        session.add(game)
        session.flush()
        assert game.id is not None
        for ply, uci in enumerate(ucis):
            move = chess.Move.from_uci(uci)
            san = board.san(move)
            board.push(move)
            by_bot = board.turn == player.chess_color  # the side that just moved is not the user
            session.add(
                Move(
                    game_id=game.id, ply=ply, uci=uci, san=san, fen_after=board.fen(), by_bot=by_bot
                )
            )
        outcome = game_outcome(board)
        game.result = outcome.result if outcome else "0-1"
        session.add(game)
        session.commit()
        return game.id


def test_40_move_game_under_60_seconds_with_full_review() -> None:
    with TestClient(create_app(_settings)) as c:
        gid = insert_game(c, "byrne_fischer_1956.pgn", PlayerColor.BLACK)  # 41 moves, 82 plies
        started = time.monotonic()
        assert c.post(f"/api/games/{gid}/analysis").status_code == 202
        while (job := c.get(f"/api/games/{gid}/analysis").json())["status"] not in (
            "done",
            "failed",
        ):
            assert time.monotonic() - started < MAX_SECONDS, f"too slow: {job}"
            time.sleep(0.2)
        elapsed = time.monotonic() - started
        assert job["status"] == "done", job
        review = c.get(f"/api/games/{gid}/review").json()

    print(f"\n82 plies analysed in {elapsed:.1f} s")
    assert elapsed < MAX_SECONDS
    assert len(review["moves"]) == 82
    assert len(review["evals"]) == 83
    assert review["opening"]["name"].startswith("Grünfeld")
    assert review["black"]["accuracy"] > review["white"]["accuracy"]
    assert 1 <= len(review["key_moments"]) <= 5
    assert all(ply % 2 == 1 for ply in review["key_moments"])  # black = the user here
