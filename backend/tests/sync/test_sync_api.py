"""Sync and background queue through the API (fake platforms, fake engine, temp DB)."""

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.main import create_app
from app.models.analysis import AnalysisJob
from app.models.game import Move
from tests.conftest import FakeEngine, factory_for, make_settings
from tests.sync.fakes import FakePlatforms, chesscom_game, lichess_game, ms

NOW = datetime.now(UTC)


@pytest.fixture
def platforms() -> FakePlatforms:
    return FakePlatforms()


@pytest.fixture
def client(
    tmp_path: Path, fake_engine: FakeEngine, platforms: FakePlatforms
) -> Iterator[TestClient]:
    settings = make_settings(
        database_url=f"sqlite:///{tmp_path / 'sync.db'}",
        sync_retry_wait_s=0.0,
        lichess_url="https://lichess.test",
        chesscom_url="https://chesscom.test",
    )
    app = create_app(
        settings,
        engine_factory=factory_for(fake_engine),
        analysis_engine_factory=factory_for(fake_engine),
        sync_client_factory=platforms.client_factory(),
    )
    with TestClient(app) as c:
        yield c


def sync(client: TestClient, older: bool = False) -> dict[str, Any]:
    assert client.post("/api/sync", json={"older": older}).status_code == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state: dict[str, Any] = client.get("/api/sync").json()
        if not state["running"]:
            return state
        time.sleep(0.02)
    raise AssertionError("sync did not finish")


def wait_queue_empty(client: TestClient) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        q = client.get("/api/queue").json()
        if q["pending"] == 0 and q["current_game_id"] is None:
            return
        time.sleep(0.05)
    raise AssertionError("queue did not finish")


def games(client: TestClient, **filters: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get("/api/games", params=filters).json()["items"]
    return items


def test_accounts_are_set_and_removed(client: TestClient) -> None:
    body = client.put("/api/accounts", json={"lichess": " Yago ", "chesscom": None}).json()
    assert [(a["platform"], a["username"]) for a in body["accounts"]] == [("lichess", "Yago")]
    assert body["sync_months"] == 6
    body = client.put("/api/accounts", json={"lichess": "", "chesscom": "yago"}).json()
    assert [a["platform"] for a in body["accounts"]] == ["chesscom"]


def test_no_accounts_no_sync(client: TestClient) -> None:
    assert client.post("/api/sync", json={}).status_code == 400


def test_first_sync_last_months_then_incremental_then_older(
    client: TestClient, platforms: FakePlatforms
) -> None:
    recent = lichess_game("recent", NOW - timedelta(days=60))
    old = lichess_game("old", NOW - timedelta(days=250), white="Rival", black="Yago")
    platforms.lichess = [recent, old, lichess_game("v", NOW - timedelta(days=5), variant="atomic")]
    client.put("/api/accounts", json={"lichess": "yago"})  # case-insensitive

    state = sync(client)
    assert state["accounts"][0]["imported"] == 1  # only the last 6 months; the variant skipped
    [game] = games(client)
    assert (game["platform"], game["player_color"], game["time_class"]) == (
        "lichess",
        "white",
        "blitz",
    )
    assert (game["white_elo"], game["black_elo"], game["external_url"]) == (
        1500,
        1600,
        "https://lichess.test/recent",
    )
    since = int(platforms.requests[-1].url.params["since"])
    assert abs(since - ms(NOW - timedelta(days=182))) < 4 * 86_400_000  # ~6 months

    # Incremental: from just after the newest game; nothing is imported twice.
    platforms.lichess.append(lichess_game("new", NOW - timedelta(days=1)))
    assert sync(client)["accounts"][0]["imported"] == 1
    assert int(platforms.requests[-1].url.params["since"]) == recent["createdAt"] + 1

    # Older games: the 6 months before the covered range (the old game, played with black).
    assert sync(client, older=True)["accounts"][0]["imported"] == 1
    assert {g["player_color"] for g in games(client)} == {"white", "black"}
    assert len(games(client)) == 3


def test_clocks_are_stored(client: TestClient, platforms: FakePlatforms, tmp_path: Path) -> None:
    platforms.lichess = [lichess_game("c", NOW - timedelta(days=3))]
    client.put("/api/accounts", json={"lichess": "Yago"})
    sync(client)
    from app.db import make_db_engine

    with Session(make_db_engine(f"sqlite:///{tmp_path / 'sync.db'}")) as session:
        clocks = session.exec(select(Move.clock_s).order_by(col(Move.ply))).all()
    assert clocks[:2] == [180.0, 178.0] and clocks[5] == 20.0


def test_chesscom_by_month_and_filters(client: TestClient, platforms: FakePlatforms) -> None:
    start = NOW - timedelta(days=20)
    platforms.chesscom = {
        (start.year, start.month): [
            chesscom_game("a", start),
            chesscom_game("b", start + timedelta(hours=1), rules="chess960"),
            chesscom_game("c", start + timedelta(hours=2), white="other", black="someone"),
        ]
    }
    client.put("/api/accounts", json={"chesscom": "Yago"})
    progress = sync(client)["accounts"][0]
    assert (progress["imported"], progress["skipped"]) == (1, 1)  # the 960 game never arrives
    assert len(games(client, platform="chesscom", time_class="rapid", result="win")) == 1
    assert games(client, platform="lichess") == []
    assert games(client, color="black") == []


def test_network_error_and_rate_limit(client: TestClient, platforms: FakePlatforms) -> None:
    start = NOW - timedelta(days=2)
    platforms.lichess = [lichess_game("l", start)]
    platforms.chesscom = {(start.year, start.month): [chesscom_game("c", start)]}
    platforms.fail = {"lichess"}
    platforms.limit_once = {"chesscom"}
    client.put("/api/accounts", json={"lichess": "Yago", "chesscom": "Yago"})
    state = sync(client)
    by = {a["platform"]: a for a in state["accounts"]}
    assert by["lichess"]["state"] == "error" and "conectar" in by["lichess"]["error"]
    assert by["chesscom"]["imported"] == 1  # retried after the 429
    accounts = {a["platform"]: a for a in client.get("/api/accounts").json()["accounts"]}
    assert accounts["lichess"]["last_error"] and accounts["chesscom"]["last_error"] is None
    # Next time it works: nothing was lost.
    platforms.fail = set()
    assert sync(client)["accounts"][0]["imported"] == 1


def test_queue_analyses_most_recent_first_and_can_pause(
    client: TestClient, platforms: FakePlatforms, tmp_path: Path
) -> None:
    platforms.lichess = [
        lichess_game("older", NOW - timedelta(days=10)),
        lichess_game("newer", NOW - timedelta(days=1)),
    ]
    client.put("/api/accounts", json={"lichess": "Yago"})
    assert client.post("/api/queue/pause").json()["paused"]
    sync(client)
    assert client.get("/api/queue").json()["pending"] == 2
    assert games(client, analysed="true") == []

    client.post("/api/queue/resume")
    wait_queue_empty(client)
    assert len(games(client, analysed="true")) == 2
    from app.db import make_db_engine

    with Session(make_db_engine(f"sqlite:///{tmp_path / 'sync.db'}")) as session:
        jobs = session.exec(select(AnalysisJob).order_by(col(AnalysisJob.finished_at))).all()
    newest = {g["id"]: g for g in games(client)}
    first = newest[jobs[0].game_id]
    assert first["external_url"].endswith("/newer")  # most recent first


def test_failed_games_are_retried_once(tmp_path: Path) -> None:
    from app.analysis.queue import _waiting
    from app.db import init_db, make_db_engine
    from app.models.analysis import AnalysisStatus
    from app.models.game import Game
    from app.play.rules import PlayerColor

    db = make_db_engine(f"sqlite:///{tmp_path / 'q.db'}")
    init_db(db)
    with Session(db) as session:
        ids = []
        for i in range(3):
            game = Game(
                player_color=PlayerColor.WHITE,
                platform="lichess",
                external_id=str(i),
                played_at=NOW - timedelta(days=i),
                result="1-0",
            )
            session.add(game)
            session.flush()
            assert game.id is not None
            ids.append(game.id)
        session.add(
            AnalysisJob(game_id=ids[1], settings_key="k", status=AnalysisStatus.FAILED, attempts=1)
        )
        session.add(
            AnalysisJob(game_id=ids[2], settings_key="k", status=AnalysisStatus.FAILED, attempts=2)
        )
        session.commit()
        assert _waiting(session) == [ids[0], ids[1]]  # the twice-failed game is given up
