"""Insights computed after an analysis, and the statistics endpoint (fake engine)."""

import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from tests.api.test_explanation import analysed
from tests.conftest import FakeEngine, factory_for, make_settings


def stats(client: TestClient, **params: Any) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/stats", params=params).json()
    return body


def test_insights_then_stats(client: TestClient, fake_engine: FakeEngine) -> None:
    analysed(client, fake_engine)  # 1. f3 e5 2. g4?? Qh4# against the bot (user = white)
    deadline = time.monotonic() + 10
    while stats(client, include_bot=True)["stats"]["games"] == 0:
        assert time.monotonic() < deadline, "insights not computed"
        time.sleep(0.05)
    body = stats(client, include_bot=True)
    s = body["stats"]
    assert (body["games_finished"], body["games_unanalysed"]) == (1, 0)
    assert s["games"] == 1 and not s["enough"]
    assert [(k["kind"], k["count"]) for k in s["kinds"]] == [("allows_mate", 1)]
    opening = next(p for p in s["phases"] if p["phase"] == "opening")
    assert opening["errors"] == 1 and opening["examples"][0]["ply"] == 2
    assert opening["examples"][0]["san"] == "g4"
    # By default only real games count: a game against the bot does not.
    assert stats(client)["stats"]["games"] == 0
    assert stats(client, color="black", include_bot=True)["stats"]["games"] == 0


def test_insights_in_a_worker_process(tmp_path: Path, fake_engine: FakeEngine) -> None:
    """The real setting: computed in a separate process (data goes there and back as dicts)."""
    app = create_app(
        make_settings(database_url=f"sqlite:///{tmp_path / 'p.db'}", insights_process=True),
        engine_factory=factory_for(fake_engine),
        analysis_engine_factory=factory_for(fake_engine),
    )
    with TestClient(app) as client:
        analysed(client, fake_engine)
        deadline = time.monotonic() + 60
        while stats(client, include_bot=True)["stats"]["games"] == 0:
            assert time.monotonic() < deadline, "insights not computed in the worker process"
            time.sleep(0.1)
        kinds = stats(client, include_bot=True)["stats"]["kinds"]
        assert [k["kind"] for k in kinds] == ["allows_mate"]
