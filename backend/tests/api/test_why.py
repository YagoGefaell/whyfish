"""'Ver por qué' and 'Pruébalo tú' endpoints (fake engine)."""

import chess
from fastapi.testclient import TestClient

from app.analysis.types import EngineLine
from tests.api.test_analysis import wait_done
from tests.api.test_explanation import analysed
from tests.conftest import FakeEngine
from tests.explain.scenarios import QUEEN_LATER, QUEEN_LATER_LINE

QUEEN_PGN = f"""[Event "Test"]
[SetUp "1"]
[FEN "{QUEEN_LATER}"]
[Result "0-1"]

1. a3 Re1+ 2. Kh2 Nf3+ 3. Kh3 Nxh4 4. Kxh4 0-1
"""


def _epd(fen: str, ucis: list[str]) -> str:
    board = chess.Board(fen)
    for uci in ucis:
        board.push_uci(uci)
    return board.epd()


def queen_game(client: TestClient, fake: FakeEngine) -> int:
    """1.a3?? with a cached refutation of only two plies (Re1+): the rest needs the engine."""
    fake.analyses[_epd(QUEEN_LATER, [])] = (
        EngineLine(("h4d4", "g8f8"), cp=300),
        EngineLine(("a2a3", "e8e1"), cp=-600),
    )
    fake.analyses[_epd(QUEEN_LATER, QUEEN_LATER_LINE[:2])] = (
        EngineLine(tuple(QUEEN_LATER_LINE[2:]), cp=-600),
    )
    gid: int = client.post(
        "/api/games/import", json={"pgn": QUEEN_PGN, "user_color": "white"}
    ).json()["game"]["id"]
    client.post(f"/api/games/{gid}/analysis")
    assert wait_done(client, gid)["status"] == "done"
    return gid


def test_refutation_is_extended_to_the_consequence_and_cached(
    client: TestClient, fake_engine: FakeEngine
) -> None:
    gid = queen_game(client, fake_engine)
    calls = len(fake_engine.analyse_calls)
    body = client.get(f"/api/games/{gid}/moves/0/why?kind=refutation").json()
    assert [s["san"] for s in body["steps"]] == ["a3", "Re1+", "Kh2", "Nf3+", "Kh3", "Nxh4", "Kxh4"]
    assert body["consequence_ply"] == 6
    assert body["steps"][5]["caption"] == "El caballo rival captura tu dama"
    assert body["summary"] == "Pierdes la dama a cambio de caballo (unos 6 peones de diferencia)."
    assert body["kind"] == "refutation" and body["tone"] == "bad" and body["step_ms"] == 1000
    extended = len(fake_engine.analyse_calls)
    assert extended == calls + 1  # one search from the end of the cached line
    client.get(f"/api/games/{gid}/moves/0/why?kind=refutation")
    assert len(fake_engine.analyse_calls) == extended  # second time: from the cache


def test_mate_and_errors(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = analysed(client, fake_engine)  # 1. f3 e5 2. g4?? Qh4#
    body = client.get(f"/api/games/{gid}/moves/2/why").json()
    assert body["summary"] == "Esta jugada permite mate inmediato."
    assert body["steps"][-1]["caption"] == "La dama rival da jaque mate"
    # g4 is not a good move, a book move has nothing to replay.
    assert client.get(f"/api/games/{gid}/moves/2/why?kind=idea").status_code == 409
    assert client.get(f"/api/games/{gid}/moves/3/why").status_code == 409
    assert client.get(f"/api/games/{gid}/moves/9/why").status_code == 404
    assert client.get(f"/api/games/{gid}/moves/2/why?kind=other").status_code == 422


def test_solution(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = analysed(client, fake_engine)
    body = client.get(f"/api/games/{gid}/moves/2/why?kind=solution").json()
    assert body["title"] == "La solución: 2.e3"
    assert body["steps"][0]["san"] == "e3" and body["tone"] == "good"


def test_try_it_yourself(client: TestClient, fake_engine: FakeEngine) -> None:
    gid = analysed(client, fake_engine)
    good = client.post(f"/api/games/{gid}/moves/2/try", json={"uci": "e2e3"}).json()
    assert good["correct"] and good["why"] is None and good["san"] == "e3"
    bad = client.post(f"/api/games/{gid}/moves/2/try", json={"uci": "g2g4"}).json()
    assert not bad["correct"] and bad["classification"] == "blunder"
    assert bad["why"]["title"] == "Por qué falla 2.g4"
    assert bad["why"]["summary"] == "Esta jugada permite mate inmediato."
    illegal = client.post(f"/api/games/{gid}/moves/2/try", json={"uci": "e2e5"})
    assert illegal.status_code == 400
