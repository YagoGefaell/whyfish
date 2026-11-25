"""Tests against the real Stockfish binary (`make test-integration`).

Search times are reduced so the whole suite stays fast. Skipped if STOCKFISH_PATH is unusable.
"""

import asyncio
import io
import random

import chess
import chess.engine
import chess.pgn
import pytest
from fastapi.testclient import TestClient

from app.config import BotLevel, Settings
from app.engine.stockfish import StockfishEngine
from app.main import create_app

# Reads STOCKFISH_PATH etc. from the environment / .env, with fast search times.
_settings = Settings(
    bot_movetime_s=0.02,
    hint_time_s=0.02,
    draw_eval_time_s=0.02,
    database_url="sqlite://",
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        _settings.stockfish_path is None or not _settings.stockfish_path.is_file(),
        reason="STOCKFISH_PATH not set or binary missing",
    ),
]

# Safety cap: random play vs the bot almost always ends far earlier.
MAX_PLAYER_MOVES = 300


async def test_start_ping_and_close() -> None:
    engine = await StockfishEngine.start(_settings)
    try:
        assert engine.name.startswith("Stockfish")
        await engine.ping()
    finally:
        await engine.close()


async def test_concurrent_pings_do_not_interfere() -> None:
    # Regression: concurrent /api/health requests used to cancel each other's ping.
    engine = await StockfishEngine.start(_settings)
    try:
        await asyncio.gather(*(engine.ping() for _ in range(5)))
        await engine.ping()
    finally:
        await engine.close()


async def test_close_is_safe_when_process_already_died() -> None:
    engine = await StockfishEngine.start(_settings)
    engine._transport.kill()
    await engine._protocol.returncode

    await engine.close()  # must not raise


def test_health_endpoint_with_real_engine() -> None:
    with TestClient(create_app(_settings)) as c:
        response = c.get("/api/health")

    assert response.status_code == 200
    assert response.json()["engine"]["name"].startswith("Stockfish")


@pytest.mark.parametrize("level", list(BotLevel))
def test_full_game_against_each_level_and_pgn(level: BotLevel) -> None:
    """Acceptance (phase 1): a complete game against every level, then a valid PGN."""
    rng = random.Random(f"whyfish-{level}")
    with TestClient(create_app(_settings)) as c:
        state = c.post(
            "/api/games", json={"color": "white", "level": level, "allow_hint": True}
        ).json()
        gid = state["id"]
        assert c.post(f"/api/games/{gid}/hint").status_code == 200

        for _ in range(MAX_PLAYER_MOVES):
            if state["status"] == "finished":
                break
            board = chess.Board(state["fen"])
            move = rng.choice(sorted(board.legal_moves, key=lambda m: m.uci()))
            response = c.post(f"/api/games/{gid}/moves", json={"uci": move.uci()})
            assert response.status_code == 200, response.text
            state = response.json()
        else:
            state = c.post(f"/api/games/{gid}/resign").json()

        assert state["status"] == "finished"
        pgn = c.get(f"/api/games/{gid}/pgn").text

    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    assert not game.errors
    assert game.headers["Result"] == state["result"]
    assert [m.uci() for m in game.mainline_moves()] == [m["uci"] for m in state["moves"]]
    assert game.end().board().fen() == state["fen"]
