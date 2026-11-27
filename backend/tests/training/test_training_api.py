"""A training session through the API (fake engine): the fool's mate blunder 2.g4??."""

import time
from typing import Any

from fastapi.testclient import TestClient

from tests.api.test_explanation import analysed
from tests.conftest import FakeEngine


def wait_insights(client: TestClient) -> None:
    deadline = time.monotonic() + 10
    while client.get("/api/stats?include_bot=true").json()["stats"]["games"] == 0:
        assert time.monotonic() < deadline
        time.sleep(0.05)


def test_session_wrong_then_right_and_streak(client: TestClient, fake_engine: FakeEngine) -> None:
    analysed(client, fake_engine)  # 1. f3 e5 2. g4?? Qh4# (user = white, against the bot)
    wait_insights(client)
    session: dict[str, Any] = client.get("/api/training/session").json()
    assert session["daily"] and len(session["positions"]) == 1 and session["current"] == 0
    item_id = session["positions"][0]["item_id"]

    exercise = client.get(f"/api/training/items/{item_id}").json()
    assert exercise["prompt"] == "Encuentra la mejor jugada" and exercise["kind"] == "error"
    assert exercise["context"] == {
        "opponent": "Stockfish (Club ~1500)",
        "origin": "contra el bot",
        "pace": None,
        "move_number": 2,
        "color": "white",
    }
    assert exercise["fen"].startswith("rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w")
    assert "e2e3" not in str(exercise)  # never the solution

    sid = session["id"]
    wrong = client.post(f"/api/training/sessions/{sid}/positions/0/attempt", json={"uci": "g2g4"})
    body = wrong.json()
    assert not body["result"]["correct"] and body["counted"]
    assert body["box"] == 1 and body["result"]["why"] is not None
    # The failed exercise comes back once at the end of the session.
    assert [p["state"] for p in body["session"]["positions"]] == ["wrong", "pending"]
    assert body["session"]["positions"][1]["repeat"] and body["session"]["current"] == 1

    right = client.post(f"/api/training/sessions/{sid}/positions/1/attempt", json={"uci": "e2e3"})
    body = right.json()
    assert body["result"]["correct"] and not body["counted"]  # the repeat does not move the box
    assert body["box"] == 1
    assert body["session"]["completed"] and body["session"]["streak"] == 1
    # The same daily session comes back (finished) for the rest of the day.
    again = client.get("/api/training/session").json()
    assert again["id"] == sid and again["completed"]


def test_settings_and_filtered_session(client: TestClient, fake_engine: FakeEngine) -> None:
    body = client.put(
        "/api/training/settings", json={"session_size": 8, "weak_new": 2, "include_bullet": True}
    ).json()
    assert body == {"session_size": 8, "weak_new": 2, "include_bullet": True}
    analysed(client, fake_engine)
    wait_insights(client)
    filtered = client.get("/api/training/session?error_kind=allows_mate&phase=opening").json()
    assert not filtered["daily"] and len(filtered["positions"]) == 1
    assert filtered["filter"] == {"error_kind": "allows_mate", "phase": "opening"}
    none = client.get("/api/training/session?error_kind=hanging").json()
    assert none["positions"] == [] and none["current"] is None
