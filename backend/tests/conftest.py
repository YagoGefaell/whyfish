from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import chess.engine
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.stockfish import Engine, EngineOptions, EngineUnavailableError
from app.main import EngineFactory, create_app


@dataclass
class PlayCall:
    fen: str
    limit: chess.engine.Limit
    options: dict[str, str | int | bool]


@dataclass
class FakeEngine:
    """Deterministic engine for unit tests.

    `play` returns the next scripted move (UCI) if any, else the first legal move in UCI order.
    `evaluate` returns `evaluation`.
    """

    engine_name: str = "FakeFish 1"
    responsive: bool = True
    alive: bool = True
    busy: bool = False
    fail_next_play: bool = False
    scripted: list[str] = field(default_factory=list)
    evaluation: chess.engine.PovScore = field(
        default_factory=lambda: chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    )
    play_calls: list[PlayCall] = field(default_factory=list)
    closed: bool = False

    @property
    def name(self) -> str:
        return self.engine_name

    @property
    def is_alive(self) -> bool:
        return self.alive

    @property
    def is_busy(self) -> bool:
        return self.busy

    async def ping(self) -> None:
        if not self.responsive:
            raise EngineUnavailableError("fake engine not responding")

    async def play(
        self, board: chess.Board, limit: chess.engine.Limit, options: EngineOptions
    ) -> chess.Move:
        self.play_calls.append(PlayCall(board.fen(), limit, dict(options)))
        if self.fail_next_play:
            self.fail_next_play = False
            raise EngineUnavailableError("fake engine crashed")
        if self.scripted:
            move = chess.Move.from_uci(self.scripted.pop(0))
            assert move in board.legal_moves, f"scripted move {move} is illegal"
            return move
        return sorted(board.legal_moves, key=lambda m: m.uci())[0]

    async def evaluate(
        self, board: chess.Board, limit: chess.engine.Limit
    ) -> chess.engine.PovScore:
        return self.evaluation

    async def close(self) -> None:
        self.closed = True


def make_settings(**overrides: object) -> Settings:
    # model_validate skips env/.env loading, so unit tests are hermetic.
    values: dict[str, object] = {"stockfish_path": None, "database_url": "sqlite://"}
    values.update(overrides)
    return Settings.model_validate(values)


def factory_for(engine: Engine) -> EngineFactory:
    async def factory(_: Settings) -> Engine:
        return engine

    return factory


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def client(settings: Settings, fake_engine: FakeEngine) -> Iterator[TestClient]:
    with TestClient(create_app(settings, engine_factory=factory_for(fake_engine))) as c:
        yield c


def play_all(client: TestClient, game_id: int, ucis: Sequence[str]) -> dict[str, Any]:
    """Play the user's moves one by one, asserting each is accepted; return the last state."""
    state: dict[str, Any] = {}
    for uci in ucis:
        response = client.post(f"/api/games/{game_id}/moves", json={"uci": uci})
        assert response.status_code == 200, response.text
        state = response.json()
    return state


@pytest.fixture
def tmp_db_settings(tmp_path: Path) -> Settings:
    return make_settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
