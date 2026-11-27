from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import chess.engine
import pytest
from fastapi.testclient import TestClient

from app.analysis.types import EngineLine
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
    evaluate_calls: int = 0
    # Analysis: lines per EPD; positions not listed get the first legal moves with cp 0.
    analyses: dict[str, tuple[EngineLine, ...]] = field(default_factory=dict)
    analyse_calls: list[chess.Board] = field(default_factory=list)
    analyse_limits: list[chess.engine.Limit] = field(default_factory=list)
    analyse_root_moves: list[tuple[chess.Move, ...] | None] = field(default_factory=list)
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
        self.evaluate_calls += 1
        return self.evaluation

    async def analyse(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
        multipv: int,
        root_moves: Sequence[chess.Move] | None = None,
    ) -> tuple[EngineLine, ...]:
        self.analyse_calls.append(board.copy())
        self.analyse_limits.append(limit)
        self.analyse_root_moves.append(tuple(root_moves) if root_moves else None)
        allowed = {m.uci() for m in root_moves} if root_moves else None
        if board.epd() in self.analyses:
            lines = self.analyses[board.epd()]
            if allowed is not None:
                # Like searchmoves: every requested move gets a line (cp 0 if not scripted).
                lines = tuple(ln for ln in lines if ln.move in allowed)
                missing = sorted(allowed - {ln.move for ln in lines})
                lines += tuple(EngineLine(moves=(uci,), cp=0) for uci in missing)
            return lines[:multipv] if allowed is not None else lines
        legal = sorted(board.legal_moves, key=lambda m: m.uci())
        if root_moves:
            legal = [m for m in legal if m in root_moves]
        return tuple(EngineLine(moves=(m.uci(),), cp=0) for m in legal[:multipv])

    async def close(self) -> None:
        self.closed = True


def make_settings(**overrides: object) -> Settings:
    # model_validate skips env/.env loading, so unit tests are hermetic.
    values: dict[str, object] = {
        "stockfish_path": None,
        "database_url": "sqlite://",
        "insights_process": False,  # a thread: no worker process per test app
    }
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
    app = create_app(
        settings,
        engine_factory=factory_for(fake_engine),
        analysis_engine_factory=factory_for(fake_engine),
    )
    with TestClient(app) as c:
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
