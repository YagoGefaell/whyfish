import asyncio

import chess
from fastapi.testclient import TestClient

from app.analysis.types import EngineLine
from app.config import Settings
from app.engine.pool import PoolManager
from tests.conftest import FakeEngine, make_settings


def test_evaluate_start_position(client: TestClient, fake_engine: FakeEngine) -> None:
    board = chess.Board()
    fake_engine.analyses[board.epd()] = (EngineLine(("e2e4", "e7e5", "g1f3"), cp=30),)
    body = client.post("/api/analysis/evaluate", json={"fen": chess.STARTING_FEN}).json()
    assert body["turn"] == "white" and body["terminal"] is None
    assert body["best_uci"] == "e2e4" and body["best_san"] == "e4"
    assert body["lines"][0]["san"] == ["e4", "e5", "Nf3"]
    assert body["white"]["cp"] == 30


def test_scores_are_flipped_for_the_eval_bar_when_black_moves(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    board = chess.Board()
    board.push_uci("e2e4")
    fake_engine.analyses[board.epd()] = (EngineLine(("e7e5",), cp=-40),)  # black is worse
    body = client.post("/api/analysis/evaluate", json={"moves": ["e2e4"]}).json()
    assert body["turn"] == "black"
    assert body["lines"][0]["cp"] == -40
    assert body["white"]["cp"] == 40 and body["white"]["win"] > 50


def test_moves_history_reaches_the_engine(client: TestClient, fake_engine: FakeEngine) -> None:
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f3g1"]
    client.post("/api/analysis/evaluate", json={"moves": moves})
    sent = fake_engine.analyse_calls[-1]
    assert [m.uci() for m in sent.move_stack] == ["g1f3", "b8c6", "f3g1"]  # reversible tail


def test_terminal_position_needs_no_engine(client: TestClient, fake_engine: FakeEngine) -> None:
    body = client.post(
        "/api/analysis/evaluate", json={"moves": ["f2f3", "e7e5", "g2g4", "d8h4"]}
    ).json()
    assert body["terminal"] == "checkmate"
    assert body["lines"] == [] and body["best_uci"] is None
    assert body["white"]["win"] == 0.0
    assert fake_engine.analyse_calls == []


def test_multipv_is_capped(client: TestClient, fake_engine: FakeEngine) -> None:
    body = client.post("/api/analysis/evaluate", json={"multipv": 50}).json()
    assert len(body["lines"]) == 5  # EVALUATE_MAX_MULTIPV


def test_invalid_input(client: TestClient) -> None:
    bad_fen = client.post("/api/analysis/evaluate", json={"fen": "nope"})
    assert bad_fen.status_code == 400 and "FEN" in bad_fen.json()["detail"]
    illegal = client.post("/api/analysis/evaluate", json={"moves": ["e2e5"]})
    assert illegal.status_code == 400 and "ilegal" in illegal.json()["detail"]


def test_pool_is_reused_and_closed_when_idle() -> None:
    started: list[FakeEngine] = []

    async def factory(_: Settings) -> FakeEngine:
        engine = FakeEngine()
        started.append(engine)
        return engine

    async def scenario() -> None:
        settings = make_settings(engine_pool_size=2, analysis_pool_idle_s=0.05)
        pools = PoolManager(factory, settings)
        async with pools.use() as pool:
            assert pool.size == 2
        async with pools.use():
            pass
        assert len(started) == 2  # reused
        await asyncio.sleep(0.15)
        assert all(e.closed for e in started)  # closed after idle
        async with pools.use():
            pass
        assert len(started) == 4  # restarted on demand
        await pools.close()

    asyncio.run(scenario())
