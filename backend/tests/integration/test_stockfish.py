"""Tests against the real Stockfish binary. Skipped if STOCKFISH_PATH is not usable."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.stockfish import StockfishEngine
from app.main import create_app

_settings = Settings()

pytestmark = [
    pytest.mark.stockfish,
    pytest.mark.skipif(
        _settings.stockfish_path is None or not _settings.stockfish_path.is_file(),
        reason="STOCKFISH_PATH not set or binary missing",
    ),
]


async def test_start_ping_and_close() -> None:
    engine = await StockfishEngine.start(_settings)
    try:
        assert engine.name.startswith("Stockfish")
        await engine.ping()
    finally:
        await engine.close()


async def test_concurrent_pings_do_not_interfere() -> None:
    # Regression: concurrent /health requests used to cancel each other's ping.
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
        response = c.get("/health")

    assert response.status_code == 200
    assert response.json()["engine"]["name"].startswith("Stockfish")
