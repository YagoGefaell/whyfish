from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.stockfish import Engine, EngineUnavailableError, StockfishEngine
from app.main import create_app
from tests.conftest import FakeEngine, factory_for


def test_health_ok_reports_engine_name(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "engine": {"status": "ok", "name": "FakeFish 1", "detail": None, "busy": False},
    }


def test_health_503_when_engine_stops_responding(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    fake_engine.responsive = False

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["engine"]["status"] == "unavailable"
    assert "not responding" in body["engine"]["detail"]


def test_health_ok_without_ping_while_engine_is_busy(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    fake_engine.busy = True
    fake_engine.responsive = False  # a ping would fail: proves we don't ping while busy

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["engine"]["busy"] is True


def test_health_503_when_busy_engine_process_died(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    fake_engine.busy = True
    fake_engine.alive = False

    assert client.get("/api/health").status_code == 503


def test_app_starts_and_reports_503_when_engine_fails_to_start(settings: Settings) -> None:
    async def failing_factory(_: Settings) -> Engine:
        raise EngineUnavailableError("boom")

    with TestClient(create_app(settings, engine_factory=failing_factory)) as c:
        response = c.get("/api/health")

    assert response.status_code == 503
    assert response.json()["engine"] == {
        "status": "unavailable",
        "name": None,
        "detail": "boom",
        "busy": False,
    }


def test_missing_stockfish_path_is_reported(settings: Settings) -> None:
    with TestClient(create_app(settings, engine_factory=StockfishEngine.start)) as c:
        response = c.get("/api/health")

    assert response.status_code == 503
    assert "STOCKFISH_PATH" in response.json()["engine"]["detail"]


def test_engine_is_closed_on_shutdown(settings: Settings, fake_engine: FakeEngine) -> None:
    with TestClient(create_app(settings, engine_factory=factory_for(fake_engine))):
        assert not fake_engine.closed
    assert fake_engine.closed
