from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.stockfish import Engine, EngineUnavailableError, StockfishEngine
from app.main import create_app
from tests.conftest import FakeEngine


def test_health_ok_reports_engine_name(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "engine": {"status": "ok", "name": "FakeFish 1", "detail": None},
    }


def test_health_503_when_engine_stops_responding(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    fake_engine.responsive = False

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["engine"]["status"] == "unavailable"
    assert "not responding" in body["engine"]["detail"]


def test_app_starts_and_reports_503_when_engine_fails_to_start(settings: Settings) -> None:
    async def failing_factory(_: Settings) -> Engine:
        raise EngineUnavailableError("boom")

    with TestClient(create_app(settings, engine_factory=failing_factory)) as c:
        response = c.get("/health")

    assert response.status_code == 503
    assert response.json()["engine"] == {"status": "unavailable", "name": None, "detail": "boom"}


def test_missing_stockfish_path_is_reported(settings: Settings) -> None:
    with TestClient(create_app(settings, engine_factory=StockfishEngine.start)) as c:
        response = c.get("/health")

    assert response.status_code == 503
    assert "STOCKFISH_PATH" in response.json()["engine"]["detail"]


def test_engine_is_closed_on_shutdown(settings: Settings, fake_engine: FakeEngine) -> None:
    async def factory(_: Settings) -> Engine:
        return fake_engine

    with TestClient(create_app(settings, engine_factory=factory)):
        assert not fake_engine.closed
    assert fake_engine.closed
