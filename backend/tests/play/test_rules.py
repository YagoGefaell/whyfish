import io
from datetime import date

import chess
import chess.engine
import chess.pgn
import pytest

from app.config import LEVEL_PRESETS, BotLevel
from app.play import rules
from app.play.rules import IllegalMoveError, InvalidFenError, PlayerColor, Termination


class TestParseMove:
    def test_legal_move(self) -> None:
        assert rules.parse_move(chess.Board(), "e2e4") == chess.Move.from_uci("e2e4")

    @pytest.mark.parametrize("uci", ["e2e5", "e7e5", "zz", "", "e1g1"])
    def test_rejects_illegal_or_malformed(self, uci: str) -> None:
        with pytest.raises(IllegalMoveError):
            rules.parse_move(chess.Board(), uci)

    def test_promotion_requires_piece(self) -> None:
        board = chess.Board("8/P6k/8/8/8/8/8/K7 w - - 0 1")
        assert rules.parse_move(board, "a7a8n").promotion == chess.KNIGHT
        with pytest.raises(IllegalMoveError):
            rules.parse_move(board, "a7a8")

    def test_castling(self) -> None:
        board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        assert board.is_castling(rules.parse_move(board, "e1g1"))


class TestGameOutcome:
    def test_ongoing(self) -> None:
        assert rules.game_outcome(chess.Board()) is None

    def test_checkmate(self) -> None:
        board = rules.board_from_moves(chess.STARTING_FEN, ["f2f3", "e7e5", "g2g4", "d8h4"])
        assert rules.game_outcome(board) == rules.Outcome("0-1", Termination.CHECKMATE)

    def test_stalemate(self) -> None:
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        assert rules.game_outcome(board) == rules.Outcome(rules.DRAW, Termination.STALEMATE)

    def test_insufficient_material(self) -> None:
        board = chess.Board("8/8/8/4k3/8/8/8/4K1N1 w - - 0 1")
        outcome = rules.game_outcome(board)
        assert outcome == rules.Outcome(rules.DRAW, Termination.INSUFFICIENT_MATERIAL)

    def test_fifty_moves(self) -> None:
        board = chess.Board("8/8/8/4k3/8/8/4R3/4K3 w - - 100 80")
        assert rules.game_outcome(board) == rules.Outcome(rules.DRAW, Termination.FIFTY_MOVES)

    def test_threefold_only_once_it_happened(self) -> None:
        cycle = ["g1f3", "g8f6", "f3g1", "f6g8"]
        # Start position has occurred twice; one more cycle minus the last ply could *claim*
        # a repetition but the game must not end yet.
        almost = rules.board_from_moves(chess.STARTING_FEN, cycle + cycle[:3])
        assert rules.game_outcome(almost) is None
        done = rules.board_from_moves(chess.STARTING_FEN, cycle * 2)
        outcome = rules.game_outcome(done)
        assert outcome == rules.Outcome(rules.DRAW, Termination.THREEFOLD_REPETITION)


class TestPliesToUndo:
    @pytest.mark.parametrize(
        ("by_bot", "expected"),
        [
            ([], 0),
            ([True], 0),  # only the bot's opening move: nothing of the player's to undo
            ([False], 1),  # player's move ended the game, no bot reply
            ([False, True], 2),
            ([True, False, True], 2),
            ([False, True, False], 1),
        ],
    )
    def test_cases(self, by_bot: list[bool], expected: int) -> None:
        assert rules.plies_to_undo(by_bot) == expected


def test_resignation_outcome() -> None:
    assert rules.resignation_outcome(PlayerColor.WHITE).result == "0-1"
    assert rules.resignation_outcome(PlayerColor.BLACK).result == "1-0"


class TestValidateStartFen:
    def test_valid_fen_is_normalized(self) -> None:
        fen = "  8/P6k/8/8/8/8/8/K7 w - - 0 1 "
        assert rules.validate_start_fen(fen) == "8/P6k/8/8/8/8/8/K7 w - - 0 1"

    @pytest.mark.parametrize("fen", ["hello", "8/8/8/8 w - - 0 1", "rnbqkbnr/pppppppp w KQkq"])
    def test_malformed(self, fen: str) -> None:
        with pytest.raises(InvalidFenError, match="formato"):
            rules.validate_start_fen(fen)

    @pytest.mark.parametrize(
        "fen",
        [
            "8/8/8/4k3/8/8/8/8 w - - 0 1",  # no white king
            "K7/8/8/8/8/8/8/K6k w - - 0 1",  # two white kings
            "4k3/8/8/8/8/8/8/P3K3 w - - 0 1",  # pawn on the first rank
            "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1",  # side not to move is in check
        ],
    )
    def test_illegal_position(self, fen: str) -> None:
        with pytest.raises(InvalidFenError, match="no es legal"):
            rules.validate_start_fen(fen)

    @pytest.mark.parametrize(
        ("fen", "reason"),
        [
            ("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3", "jaque mate"),
            ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", "ahogado"),
            ("8/8/8/4k3/8/8/8/4K3 w - - 0 1", "material insuficiente"),
        ],
    )
    def test_finished_position(self, fen: str, reason: str) -> None:
        with pytest.raises(InvalidFenError, match=f"terminada \\({reason}\\)"):
            rules.validate_start_fen(fen)


def _shuffle_knights(plies: int, fen: str = chess.STARTING_FEN) -> chess.Board:
    cycle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    return rules.board_from_moves(fen, [cycle[i % 4] for i in range(plies)])


@pytest.mark.parametrize(("plies", "too_early"), [(0, True), (39, True), (40, False), (55, False)])
def test_draw_too_early_counts_full_moves_played(plies: int, too_early: bool) -> None:
    assert rules.draw_too_early(_shuffle_knights(plies), min_moves=20) is too_early


def test_draw_too_early_ignores_fen_move_number() -> None:
    late_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 60"
    assert rules.draw_too_early(_shuffle_knights(10, late_fen), min_moves=20) is True
    assert rules.draw_too_early(_shuffle_knights(40, late_fen), min_moves=20) is False


class TestShouldAcceptDraw:
    @pytest.mark.parametrize(
        ("score", "accepted"),
        [
            (chess.engine.Cp(30), True),
            (chess.engine.Cp(31), False),
            (chess.engine.Cp(-200), True),
            (chess.engine.Mate(3), False),
            (chess.engine.Mate(-3), True),
        ],
    )
    def test_from_bot_point_of_view(self, score: chess.engine.Score, accepted: bool) -> None:
        pov = chess.engine.PovScore(score, chess.BLACK)  # bot plays black
        assert rules.should_accept_draw(pov, chess.BLACK, max_cp=30) is accepted

    def test_score_reported_from_other_side_is_flipped(self) -> None:
        # +100 for white means -100 for the bot (black): the bot is worse, so it accepts.
        pov = chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE)
        assert rules.should_accept_draw(pov, chess.BLACK, max_cp=30) is True


class TestBotSearch:
    def test_skill_level_preset(self) -> None:
        limit, options = rules.bot_search(LEVEL_PRESETS[BotLevel.BEGINNER], movetime_s=1.0)
        assert limit.depth == 1 and limit.time == 1.0
        assert options == {"UCI_LimitStrength": False, "Skill Level": 0}

    def test_elo_preset(self) -> None:
        limit, options = rules.bot_search(LEVEL_PRESETS[BotLevel.CLUB], movetime_s=0.5)
        assert limit.depth is None and limit.time == 0.5
        assert options["UCI_LimitStrength"] is True and options["UCI_Elo"] == 1500

    def test_max_preset_is_full_strength(self) -> None:
        _, options = rules.bot_search(LEVEL_PRESETS[BotLevel.MAX], movetime_s=1.0)
        assert options == rules.FULL_STRENGTH_OPTIONS

    def test_every_level_has_a_preset(self) -> None:
        assert set(LEVEL_PRESETS) == set(BotLevel)


class TestBuildPgn:
    def _data(self, **overrides: object) -> rules.PgnData:
        values: dict[str, object] = {
            "white": "Jugador",
            "black": "Stockfish (Club ~1500)",
            "played_on": date(2026, 11, 25),
            "initial_fen": chess.STARTING_FEN,
            "ucis": ["f2f3", "e7e5", "g2g4", "d8h4"],
            "result": "0-1",
        }
        values.update(overrides)
        return rules.PgnData(**values)  # type: ignore[arg-type]

    def test_round_trip(self) -> None:
        game = chess.pgn.read_game(io.StringIO(rules.build_pgn(self._data())))
        assert game is not None
        assert game.headers["White"] == "Jugador"
        assert game.headers["Result"] == "0-1"
        assert game.headers["Date"] == "2026.11.25"
        assert [m.uci() for m in game.mainline_moves()] == ["f2f3", "e7e5", "g2g4", "d8h4"]
        assert "Assists" not in game.headers

    def test_ongoing_game_is_unterminated(self) -> None:
        pgn = rules.build_pgn(self._data(ucis=["e2e4"], result=None))
        assert '[Result "*"]' in pgn and '[Termination "unterminated"]' in pgn

    def test_assists_header(self) -> None:
        pgn = rules.build_pgn(self._data(undo_count=2, hint_count=1))
        assert '[Assists "undo:2 hint:1"]' in pgn

    def test_custom_start_position(self) -> None:
        fen = "8/P6k/8/8/8/8/8/K7 w - - 0 1"
        game = chess.pgn.read_game(
            io.StringIO(rules.build_pgn(self._data(initial_fen=fen, ucis=["a7a8q"], result=None)))
        )
        assert game is not None
        assert game.headers["SetUp"] == "1"
        assert game.headers["FEN"] == fen
        assert game.end().board().piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)
