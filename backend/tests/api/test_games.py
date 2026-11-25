import io
from typing import Any

import chess
import chess.engine
import chess.pgn
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.stockfish import Engine, EngineUnavailableError
from app.main import create_app
from tests.conftest import FakeEngine, factory_for, make_settings, play_all


def create(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/api/games", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def test_levels(client: TestClient) -> None:
    levels = client.get("/api/levels").json()
    assert [lvl["id"] for lvl in levels] == ["beginner", "novice", "club", "strong", "max"]
    assert levels[0]["label"] == "Principiante ~800"


class TestCreate:
    def test_as_white_waits_for_player(self, client: TestClient) -> None:
        game = create(client, color="white", level="club")
        assert game["status"] == "ongoing"
        assert game["moves"] == []
        assert game["turn"] == "white"
        assert game["fen"] == chess.STARTING_FEN
        assert game["bot_level_label"] == "Club ~1500"

    def test_as_black_bot_moves_first(self, client: TestClient, fake_engine: FakeEngine) -> None:
        fake_engine.scripted = ["e2e4"]
        game = create(client, color="black", level="max")
        assert [m["san"] for m in game["moves"]] == ["e4"]
        assert game["moves"][0]["by_bot"] is True
        assert game["turn"] == "black"

    def test_random_color(self, client: TestClient) -> None:
        game = create(client, color="random")
        assert game["player_color"] in ("white", "black")

    def test_bot_uses_level_options(self, client: TestClient, fake_engine: FakeEngine) -> None:
        create(client, color="black", level="strong")
        call = fake_engine.play_calls[0]
        assert call.options["UCI_Elo"] == 2000
        assert call.limit.time == 1.0


class TestMoves:
    def test_move_gets_bot_reply(self, client: TestClient, fake_engine: FakeEngine) -> None:
        game = create(client, color="white")
        fake_engine.scripted = ["e7e5"]
        state = play_all(client, game["id"], ["e2e4"])
        assert [(m["san"], m["by_bot"]) for m in state["moves"]] == [
            ("e4", False),
            ("e5", True),
        ]
        assert state["turn"] == "white"

    def test_illegal_move_is_rejected_and_not_saved(self, client: TestClient) -> None:
        game = create(client, color="white")
        response = client.post(f"/api/games/{game['id']}/moves", json={"uci": "e2e5"})
        assert response.status_code == 400
        assert client.get(f"/api/games/{game['id']}").json()["moves"] == []

    def test_unknown_game(self, client: TestClient) -> None:
        assert client.get("/api/games/999").status_code == 404
        assert client.post("/api/games/999/moves", json={"uci": "e2e4"}).status_code == 404

    def test_bot_mates_player(self, client: TestClient, fake_engine: FakeEngine) -> None:
        game = create(client, color="white")
        fake_engine.scripted = ["e7e5", "d8h4"]
        state = play_all(client, game["id"], ["f2f3", "g2g4"])
        assert state["status"] == "finished"
        assert state["result"] == "0-1"
        assert state["termination"] == "checkmate"
        again = client.post(f"/api/games/{game['id']}/moves", json={"uci": "e1f2"})
        assert again.status_code == 409

    def test_player_mates_bot_without_asking_engine(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white")
        fake_engine.scripted = ["e7e5", "b8c6", "g8f6"]
        state = play_all(client, game["id"], ["e2e4", "f1c4", "d1h5", "h5f7"])
        assert (state["result"], state["termination"]) == ("1-0", "checkmate")
        assert len(fake_engine.play_calls) == 3
        assert state["moves"][-1]["san"] == "Qxf7#"

    def test_threefold_repetition_ends_game(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white")
        fake_engine.scripted = ["g8f6", "f6g8"] * 2
        state = play_all(client, game["id"], ["g1f3", "f3g1"] * 2)
        assert (state["result"], state["termination"]) == ("1/2-1/2", "threefold_repetition")

    def test_engine_failure_does_not_persist_player_move(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white")
        fake_engine.fail_next_play = True
        response = client.post(f"/api/games/{game['id']}/moves", json={"uci": "e2e4"})
        assert response.status_code == 503
        assert client.get(f"/api/games/{game['id']}").json()["moves"] == []


PROMOTION_FEN = "8/P6k/8/8/8/8/8/K7 w - - 0 1"
START_AT_MOVE_19 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 19"
START_AT_MOVE_20 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 20"


class TestStartFromFen:
    def test_player_to_move(self, client: TestClient) -> None:
        game = create(client, color="white", fen=PROMOTION_FEN)
        assert (game["initial_fen"], game["fen"]) == (PROMOTION_FEN, PROMOTION_FEN)
        assert game["moves"] == []
        assert game["turn"] == "white"

    def test_bot_to_move_plays_first(self, client: TestClient, fake_engine: FakeEngine) -> None:
        fen = "8/P6k/8/8/8/8/8/K7 b - - 0 1"
        fake_engine.scripted = ["h7g7"]
        game = create(client, color="white", fen=fen)
        assert [(m["san"], m["by_bot"]) for m in game["moves"]] == [("Kg7", True)]
        assert game["turn"] == "white"

    def test_player_promotes(self, client: TestClient) -> None:
        game = create(client, color="white", fen=PROMOTION_FEN)
        state = play_all(client, game["id"], ["a7a8n"])
        assert state["moves"][0]["san"] == "a8=N"

    def test_blank_fen_means_standard_start(self, client: TestClient) -> None:
        assert create(client, fen="   ")["fen"] == chess.STARTING_FEN

    def test_invalid_fen_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/games", json={"fen": "not a fen"})
        assert response.status_code == 400
        assert response.json()["detail"] == "El FEN no tiene un formato válido."
        assert client.get("/api/games").json() == []

    def test_finished_position_is_rejected(self, client: TestClient) -> None:
        mate = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        response = client.post("/api/games", json={"fen": mate})
        assert response.status_code == 400
        assert "terminada" in response.json()["detail"]

    def test_pgn_has_setup_and_fen_tags(self, client: TestClient) -> None:
        game = create(client, color="white", fen=PROMOTION_FEN)
        play_all(client, game["id"], ["a7a8q"])
        pgn = client.get(f"/api/games/{game['id']}/pgn").text
        assert '[SetUp "1"]' in pgn
        assert f'[FEN "{PROMOTION_FEN}"]' in pgn
        parsed = chess.pgn.read_game(io.StringIO(pgn))
        assert parsed is not None
        assert [m.uci() for m in parsed.mainline_moves()][:1] == ["a7a8q"]  # + bot reply

    def test_standard_start_pgn_has_no_setup_tags(self, client: TestClient) -> None:
        game = create(client, color="white")
        pgn = client.get(f"/api/games/{game['id']}/pgn").text
        assert "SetUp" not in pgn and "[FEN" not in pgn


class TestAssists:
    def test_hint_disabled_by_default(self, client: TestClient) -> None:
        game = create(client, color="white")
        assert client.post(f"/api/games/{game['id']}/hint").status_code == 409

    def test_hint_returns_piece_square_at_full_strength(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white", level="beginner", allow_hint=True)
        fake_engine.scripted = ["g1f3"]
        response = client.post(f"/api/games/{game['id']}/hint")
        assert response.json() == {"square": "g1"}
        assert fake_engine.play_calls[-1].options == {"UCI_LimitStrength": False, "Skill Level": 20}
        assert client.get(f"/api/games/{game['id']}").json()["hint_count"] == 1

    def test_undo_disabled_by_default(self, client: TestClient) -> None:
        game = create(client, color="white")
        play_all(client, game["id"], ["e2e4"])
        assert client.post(f"/api/games/{game['id']}/undo").status_code == 409

    def test_undo_takes_back_player_and_bot_moves(self, client: TestClient) -> None:
        game = create(client, color="white", allow_undo=True)
        play_all(client, game["id"], ["e2e4", "d2d4"])
        state = client.post(f"/api/games/{game['id']}/undo").json()
        assert [m["uci"] for m in state["moves"]][:1] == ["e2e4"]
        assert len(state["moves"]) == 2
        assert state["turn"] == "white"
        assert state["undo_count"] == 1

    def test_undo_with_only_bot_opening_move(self, client: TestClient) -> None:
        game = create(client, color="black", allow_undo=True)
        assert client.post(f"/api/games/{game['id']}/undo").status_code == 409


class TestEndings:
    def test_resign(self, client: TestClient) -> None:
        game = create(client, color="black")
        state = client.post(f"/api/games/{game['id']}/resign").json()
        assert (state["result"], state["termination"]) == ("1-0", "resignation")
        assert client.post(f"/api/games/{game['id']}/resign").status_code == 409

    def test_draw_declined_before_move_20_without_asking_engine(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white", fen=START_AT_MOVE_19)
        fake_engine.evaluation = chess.engine.PovScore(chess.engine.Cp(-500), chess.BLACK)
        body = client.post(f"/api/games/{game['id']}/draw").json()
        assert body["accepted"] is False
        assert (body["declined_reason"], body["min_fullmove"]) == ("too_early", 20)
        assert body["game"]["status"] == "ongoing"
        assert fake_engine.evaluate_calls == 0

    def test_draw_accepted_from_move_20_when_bot_not_better(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white", fen=START_AT_MOVE_20)
        fake_engine.evaluation = chess.engine.PovScore(chess.engine.Cp(20), chess.BLACK)
        body = client.post(f"/api/games/{game['id']}/draw").json()
        assert (body["accepted"], body["declined_reason"]) == (True, None)
        assert (body["game"]["result"], body["game"]["termination"]) == ("1/2-1/2", "draw_agreed")

    def test_draw_declined_when_bot_better(
        self, client: TestClient, fake_engine: FakeEngine
    ) -> None:
        game = create(client, color="white", fen=START_AT_MOVE_20)
        fake_engine.evaluation = chess.engine.PovScore(chess.engine.Cp(150), chess.BLACK)
        body = client.post(f"/api/games/{game['id']}/draw").json()
        assert (body["accepted"], body["declined_reason"]) == (False, "position")
        assert body["game"]["status"] == "ongoing"

    def test_draw_min_move_is_configurable(self, fake_engine: FakeEngine) -> None:
        settings = make_settings(draw_min_fullmove=1)
        with TestClient(create_app(settings, engine_factory=factory_for(fake_engine))) as c:
            game = create(c, color="white")
            body = c.post(f"/api/games/{game['id']}/draw").json()
        assert body["accepted"] is True


class TestPgnAndHistory:
    def test_pgn_download(self, client: TestClient, fake_engine: FakeEngine) -> None:
        game = create(client, color="white", allow_hint=True)
        client.post(f"/api/games/{game['id']}/hint")
        fake_engine.scripted = ["e7e5", "d8h4"]
        play_all(client, game["id"], ["f2f3", "g2g4"])

        response = client.get(f"/api/games/{game['id']}/pgn")
        assert response.status_code == 200
        assert f'filename="whyfish-{game["id"]}.pgn"' in response.headers["content-disposition"]
        parsed = chess.pgn.read_game(io.StringIO(response.text))
        assert parsed is not None
        assert parsed.headers["White"] == "Jugador"
        assert parsed.headers["Black"] == "Stockfish (Club ~1500)"
        assert parsed.headers["Result"] == "0-1"
        assert parsed.headers["Assists"] == "undo:0 hint:1"
        assert len(list(parsed.mainline_moves())) == 4

    def test_history_newest_first_with_move_counts(self, client: TestClient) -> None:
        first = create(client, color="white")
        play_all(client, first["id"], ["e2e4"])
        second = create(client, color="white")
        games = client.get("/api/games").json()
        assert [(g["id"], g["move_count"]) for g in games] == [(second["id"], 0), (first["id"], 2)]


def test_reload_restores_game_exactly(tmp_db_settings: Settings) -> None:
    """Reloading /play/:id mid-game: a fresh app on the same DB returns the same state."""
    engine = FakeEngine(scripted=["e7e5", "b8c6", "g8f6"])
    with TestClient(create_app(tmp_db_settings, engine_factory=factory_for(engine))) as c:
        game = create(c, color="white", level="novice", allow_undo=True, allow_hint=True)
        gid = game["id"]
        play_all(c, gid, ["e2e4", "g1f3"])
        c.post(f"/api/games/{gid}/undo")
        play_all(c, gid, ["f1c4"])
        engine.scripted = ["d2d4"]  # hint suggestion
        c.post(f"/api/games/{gid}/hint")
        before = c.get(f"/api/games/{gid}").json()

    # Restart: new app instance, new (failing) engine, same database file.
    async def no_engine(_: Settings) -> Engine:
        raise EngineUnavailableError("not needed to read a game")

    with TestClient(create_app(tmp_db_settings, engine_factory=no_engine)) as c:
        after = c.get(f"/api/games/{gid}").json()

    assert after == before
    assert after["fen"] == before["fen"]
    assert after["turn"] == "white"
    # The undo also took back the bot's Nc6, so its next scripted reply was Nf6.
    assert [m["san"] for m in after["moves"]] == ["e4", "e5", "Bc4", "Nf6"]
    assert (after["undo_count"], after["hint_count"]) == (1, 1)
    assert (after["allow_undo"], after["allow_hint"]) == (True, True)
    assert after["bot_level"] == "novice"


def test_commands_need_engine_but_reads_do_not(tmp_db_settings: Settings) -> None:
    with TestClient(create_app(tmp_db_settings, engine_factory=factory_for(FakeEngine()))) as c:
        gid = create(c, color="white")["id"]

    async def no_engine(_: Settings) -> Engine:
        raise EngineUnavailableError("down")

    with TestClient(create_app(tmp_db_settings, engine_factory=no_engine)) as c:
        assert c.get(f"/api/games/{gid}").status_code == 200
        assert c.get(f"/api/games/{gid}/pgn").status_code == 200
        assert c.get("/api/games").status_code == 200
        assert c.post(f"/api/games/{gid}/moves", json={"uci": "e2e4"}).status_code == 503
        assert c.post("/api/games", json={}).status_code == 503
