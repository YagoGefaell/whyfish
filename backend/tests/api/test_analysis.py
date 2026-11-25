import time
from typing import Any

import chess
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.main import create_app
from app.models.analysis import AnalysisJob, AnalysisStatus
from tests.conftest import FakeEngine, factory_for, make_settings, play_all

FOOLS_MATE = ["f2f3", "g2g4"]  # user (white) moves; bot replies e7e5, d8h4#


def finished_game(client: TestClient, fake: FakeEngine) -> int:
    gid: int = client.post("/api/games", json={"color": "white"}).json()["id"]
    fake.scripted = ["e7e5", "d8h4"]
    play_all(client, gid, FOOLS_MATE)
    return gid


def wait_done(client: TestClient, gid: int, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job: dict[str, Any] = client.get(f"/api/games/{gid}/analysis").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("analysis did not finish")


def test_only_finished_games(client: TestClient) -> None:
    gid = client.post("/api/games", json={"color": "white"}).json()["id"]
    response = client.post(f"/api/games/{gid}/analysis")
    assert response.status_code == 409
    assert response.json()["detail"] == "Solo se pueden analizar partidas terminadas."


def test_unknown_game(client: TestClient) -> None:
    assert client.post("/api/games/99/analysis").status_code == 404
    assert client.get("/api/games/99/analysis").status_code == 404
    assert client.get("/api/games/99/review").status_code == 404


def test_review_before_analysis(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = finished_game(client, fake_engine)
    response = client.get(f"/api/games/{gid}/review")
    assert response.status_code == 409


def test_analyse_and_review(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = finished_game(client, fake_engine)
    response = client.post(f"/api/games/{gid}/analysis")
    assert response.status_code == 202
    job = wait_done(client, gid)
    # 5 positions; the final one (checkmate) needs no engine.
    assert (job["status"], job["done"], job["total"]) == ("done", 4, 4)

    review = client.get(f"/api/games/{gid}/review").json()
    assert review["perspective"] == "white"
    assert [m["san"] for m in review["moves"]] == ["f3", "e5", "g4", "Qh4#"]
    assert len(review["evals"]) == 5
    assert review["evals"][-1]["win"] == 0.0  # white is mated
    assert set(review["white"]["counts"]) >= {"blunder", "best", "brilliant"}
    for move in review["moves"]:
        assert move["symbol"] is not None and 0 <= move["accuracy"] <= 100
    # Key moments only come from the user's (white) moves.
    assert all(ply % 2 == 0 for ply in review["key_moments"])


def test_second_request_reuses_finished_analysis(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    gid = finished_game(client, fake_engine)
    client.post(f"/api/games/{gid}/analysis")
    wait_done(client, gid)
    calls = len(fake_engine.analyse_calls)
    again = client.post(f"/api/games/{gid}/analysis")
    assert again.status_code == 200 and again.json()["status"] == "done"
    assert len(fake_engine.analyse_calls) == calls


def test_cache_is_shared_between_games(client: TestClient, fake_engine: FakeEngine) -> None:
    first = finished_game(client, fake_engine)
    client.post(f"/api/games/{first}/analysis")
    wait_done(client, first)
    calls = len(fake_engine.analyse_calls)

    second = finished_game(client, fake_engine)  # same moves -> same positions
    client.post(f"/api/games/{second}/analysis")
    job = wait_done(client, second)
    assert job["status"] == "done"
    assert len(fake_engine.analyse_calls) == calls


def test_engine_receives_reversible_history(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = client.post("/api/games", json={"color": "white"}).json()["id"]
    fake_engine.scripted = ["g8f6", "f6g8"] * 2
    play_all(client, gid, ["g1f3", "f3g1"] * 2)  # ends by threefold repetition
    client.post(f"/api/games/{gid}/analysis")
    assert wait_done(client, gid)["status"] == "done"
    longest = max(fake_engine.analyse_calls, key=lambda b: len(b.move_stack))
    assert len(longest.move_stack) == 7  # all knight moves (the last position is terminal)
    assert longest.root().fen() == chess.STARTING_FEN


def test_sse_stream_reports_done(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = finished_game(client, fake_engine)
    client.post(f"/api/games/{gid}/analysis")
    wait_done(client, gid)
    with client.stream("GET", f"/api/games/{gid}/analysis/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: done" in body
    assert '"status":"done"' in body.replace(" ", "")


def test_sse_without_analysis(client: TestClient) -> None:
    assert client.get("/api/games/1/analysis/stream").status_code == 404


def test_engine_failure_marks_job_failed(fake_engine: FakeEngine) -> None:
    async def broken(_: Settings) -> FakeEngine:
        raise RuntimeError("no engine")

    app = create_app(
        make_settings(),
        engine_factory=factory_for(fake_engine),
        analysis_engine_factory=broken,
    )
    with TestClient(app) as c:
        gid = finished_game(c, fake_engine)
        c.post(f"/api/games/{gid}/analysis")
        job = wait_done(c, gid)
    assert job["status"] == "failed" and "no engine" in job["error"]


def test_interrupted_jobs_are_marked_failed_on_startup(
    tmp_db_settings: Settings, fake_engine: FakeEngine
) -> None:
    app = create_app(tmp_db_settings, engine_factory=factory_for(fake_engine))
    with TestClient(app) as c:
        gid = finished_game(c, fake_engine)
        with Session(c.app.state.db_engine) as session:  # type: ignore[attr-defined]
            session.add(AnalysisJob(game_id=gid, settings_key="x", status=AnalysisStatus.RUNNING))
            session.commit()

    with TestClient(create_app(tmp_db_settings, engine_factory=factory_for(fake_engine))) as c:
        job = c.get(f"/api/games/{gid}/analysis").json()
        assert job["status"] == "failed"
        assert "interrumpido" in job["error"]
        # It can be started again.
        assert c.post(f"/api/games/{gid}/analysis").status_code == 202
