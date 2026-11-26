from fastapi.testclient import TestClient

from app.analysis.types import EngineLine
from tests.api.test_analysis import finished_game, wait_done
from tests.conftest import FakeEngine

# Positions of the fool's mate game (user = white): 1. f3 e5 2. g4 Qh4#.
AFTER_F3_E5 = "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq -"
AFTER_G4 = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq -"


def analysed(client: TestClient, fake: FakeEngine) -> int:
    fake.analyses[AFTER_F3_E5] = (
        EngineLine(("e2e3", "d8h4"), cp=-60),
        EngineLine(("g2g4", "d8h4"), mate=-1),
    )
    fake.analyses[AFTER_G4] = (EngineLine(("d8h4",), mate=1),)
    gid = finished_game(client, fake)
    client.post(f"/api/games/{gid}/analysis")
    assert wait_done(client, gid)["status"] == "done"
    return gid


def test_explanation_of_a_blunder(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = analysed(client, fake_engine)
    body = client.get(f"/api/games/{gid}/moves/2/explanation").json()
    assert body["ply"] == 2 and body["level"] == 1
    assert body["idea"] == "allows_mate"
    assert body["text"] == "Esta jugada permite mate inmediato: [[Qh4#]]. Había que jugar [[e3]]."
    assert body["refs"] == [
        {"san": "Qh4#", "line": "played", "base": 2, "path": ["g2g4", "d8h4"]},
        {"san": "e3", "line": "best", "base": 2, "path": ["e2e3"]},
    ]
    assert {
        "kind": "arrow",
        "role": "threat",
        "square": None,
        "from_square": "d8",
        "to_square": "h4",
    } in body["annotations"]


def test_book_move(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = analysed(client, fake_engine)
    body = client.get(f"/api/games/{gid}/moves/3/explanation").json()
    # The opening dataset names this line (it is theory, even if it is a trap).
    assert body["text"] == "Jugada de teoría: Barnes Opening: Fool's Mate."


def test_level_2(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = analysed(client, fake_engine)
    body = client.get(f"/api/games/{gid}/moves/2/explanation?level=2").json()
    assert body["level"] == 2
    assert body["text"].count("\n\n") >= 2
    assert len(body["refs"]) == body["text"].count("[[")


def test_errors(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = finished_game(client, fake_engine)
    assert client.get(f"/api/games/{gid}/moves/0/explanation").status_code == 409
    client.post(f"/api/games/{gid}/analysis")
    wait_done(client, gid)
    assert client.get(f"/api/games/{gid}/moves/9/explanation").status_code == 404
    assert client.get(f"/api/games/{gid}/moves/0/explanation?level=3").status_code == 422
    assert client.get("/api/games/99/moves/0/explanation").status_code == 404
