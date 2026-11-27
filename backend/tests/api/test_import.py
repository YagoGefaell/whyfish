import io
from typing import Any

import chess.pgn
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeEngine, factory_for, make_settings

OPERA = """[Event "Paris Opera"]
[Date "1858.11.02"]
[White "Paul Morphy"]
[Black "Duke Karl"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
"""


def import_pgn(client: TestClient, **body: Any) -> Any:
    return client.post("/api/games/import", json=body)


def test_import_with_explicit_color(client: TestClient) -> None:
    response = import_pgn(client, pgn=OPERA, user_color="black")
    assert response.status_code == 201
    body = response.json()
    game = body["game"]
    assert body["warnings"] == []
    assert game["source"] == "imported"
    assert game["player_color"] == "black"
    assert (game["white_name"], game["black_name"]) == ("Paul Morphy", "Duke Karl")
    assert (game["event"], game["played_date"]) == ("Paris Opera", "1858.11.02")
    assert game["bot_level"] is None
    assert (game["result"], game["termination"], game["status"]) == ("1-0", "checkmate", "finished")
    assert len(game["moves"]) == 33
    # "Bot" moves are the opponent's: white's here.
    assert game["moves"][0]["by_bot"] is True and game["moves"][1]["by_bot"] is False


def test_color_detected_from_player_name(fake_engine: FakeEngine) -> None:
    app = create_app(
        make_settings(player_name="paul morphy"), engine_factory=factory_for(fake_engine)
    )
    with TestClient(app) as c:
        response = import_pgn(c, pgn=OPERA)
    assert response.status_code == 201
    assert response.json()["game"]["player_color"] == "white"


def test_color_required_when_it_cannot_be_detected(client: TestClient) -> None:
    response = import_pgn(client, pgn=OPERA)
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "color_required",
        "message": "No se pudo deducir qué color jugaste. Indícalo.",
        "white": "Paul Morphy",
        "black": "Duke Karl",
    }
    assert client.get("/api/games").json()["items"] == []


def test_invalid_pgn(client: TestClient) -> None:
    response = import_pgn(client, pgn="1. e4 e5 2. Ke3", user_color="white")
    assert response.status_code == 400
    assert "no válidas" in response.json()["detail"]


def test_several_games_warns(client: TestClient) -> None:
    response = import_pgn(client, pgn=OPERA + "\n" + OPERA, user_color="white")
    assert response.json()["warnings"] == [
        "El PGN contiene 2 partidas; solo se ha importado la primera."
    ]


def test_imported_game_cannot_be_played(client: TestClient) -> None:
    gid = import_pgn(client, pgn="1. e4 *", user_color="white").json()["game"]["id"]
    response = client.post(f"/api/games/{gid}/moves", json={"uci": "e7e5"})
    assert response.status_code == 409


def test_unfinished_imported_game_can_be_analysed(client: TestClient) -> None:
    gid = import_pgn(client, pgn="1. e4 e5 *", user_color="white").json()["game"]["id"]
    assert client.post(f"/api/games/{gid}/analysis").status_code == 202


def test_pgn_export_keeps_the_original_headers(client: TestClient) -> None:
    gid = import_pgn(client, pgn=OPERA, user_color="white").json()["game"]["id"]
    parsed = chess.pgn.read_game(io.StringIO(client.get(f"/api/games/{gid}/pgn").text))
    assert parsed is not None
    assert parsed.headers["White"] == "Paul Morphy"
    assert parsed.headers["Event"] == "Paris Opera"
    assert parsed.headers["Date"] == "1858.11.02"


def test_history_shows_source_names_and_analysis_status(client: TestClient) -> None:
    gid = import_pgn(client, pgn=OPERA, user_color="white").json()["game"]["id"]
    [summary] = client.get("/api/games").json()["items"]
    assert (summary["source"], summary["white_name"], summary["analysis_status"]) == (
        "imported",
        "Paul Morphy",
        None,
    )
    client.post(f"/api/games/{gid}/analysis")
    assert client.get("/api/games").json()["items"][0]["analysis_status"] in (
        "pending",
        "running",
        "done",
    )
    assert client.get(f"/api/games/{gid}").json()["analysis_status"] is not None
