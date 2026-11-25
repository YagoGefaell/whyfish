from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.stockfish import Engine, EngineUnavailableError
from app.main import create_app


class FakeEngine:
    def __init__(self, name: str = "FakeFish 1", responsive: bool = True) -> None:
        self._name = name
        self.responsive = responsive
        self.closed = False

    @property
    def name(self) -> str:
        return self._name

    async def ping(self) -> None:
        if not self.responsive:
            raise EngineUnavailableError("fake engine not responding")

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def settings() -> Settings:
    # Ignore the developer's .env so unit tests are hermetic.
    return Settings(_env_file=None, stockfish_path=None)


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def client(settings: Settings, fake_engine: FakeEngine) -> Iterator[TestClient]:
    async def factory(_: Settings) -> Engine:
        return fake_engine

    with TestClient(create_app(settings, engine_factory=factory)) as c:
        yield c
