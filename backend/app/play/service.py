"""Game orchestration: rules + injected engine + persistence.

Chess logic lives in `rules.py` (pure). This module loads/saves games and asks the engine
for moves; nothing is persisted if the engine fails mid-operation.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import chess
import chess.engine
from sqlmodel import Session, col, func, select

from app.config import LEVEL_PRESETS, BotLevel, Settings
from app.engine.stockfish import Engine
from app.models.analysis import AnalysisJob, AnalysisStatus
from app.models.game import Game, GameSource, Move, utcnow
from app.play import rules
from app.play.pgn import ParsedPgn, pgn_result
from app.play.rules import DrawDecline, Outcome, PlayerColor


class ColorChoice(StrEnum):
    WHITE = "white"
    BLACK = "black"
    RANDOM = "random"


class GameNotFoundError(LookupError):
    pass


class GameRuleError(Exception):
    """The request is not allowed in the game's current state (user-facing, Spanish)."""


@dataclass(frozen=True)
class LoadedGame:
    game: Game
    moves: Sequence[Move]
    board: chess.Board

    @property
    def is_player_turn(self) -> bool:
        return self.board.turn == self.game.player_color.chess_color


class GameRepository:
    """Persistence for games and their moves. No engine needed."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self, game_id: int) -> LoadedGame:
        game = self._session.get(Game, game_id)
        if game is None:
            raise GameNotFoundError(game_id)
        moves = self._session.exec(
            select(Move).where(Move.game_id == game_id).order_by(col(Move.ply))
        ).all()
        board = rules.board_from_moves(game.initial_fen, [m.uci for m in moves])
        return LoadedGame(game=game, moves=moves, board=board)

    def list_with_move_counts(self) -> list[tuple[Game, int]]:
        rows = self._session.exec(
            select(Game, func.count(col(Move.id)))
            .join(Move, isouter=True)
            .group_by(col(Game.id))
            .order_by(col(Game.created_at).desc())
        ).all()
        return [(game, count) for game, count in rows]

    def analysis_statuses(self) -> dict[int, AnalysisStatus]:
        jobs = self._session.exec(select(AnalysisJob)).all()
        return {job.game_id: job.status for job in jobs}

    def analysis_status(self, game_id: int) -> AnalysisStatus | None:
        job = self._session.exec(select(AnalysisJob).where(AnalysisJob.game_id == game_id)).first()
        return job.status if job else None

    def save(self, game: Game, new_moves: Sequence[Move] = ()) -> None:
        self._session.add(game)
        self._session.flush()  # assigns game.id on creation
        for move in new_moves:
            assert game.id is not None
            move.game_id = game.id
            self._session.add(move)
        self._session.commit()

    def delete_moves(self, moves: Sequence[Move]) -> None:
        for move in moves:
            self._session.delete(move)


def game_pgn(loaded: LoadedGame, player_name: str) -> str:
    game = loaded.game
    if game.source is GameSource.IMPORTED:
        white, black = game.white_name or "?", game.black_name or "?"
    else:
        level = LEVEL_PRESETS[game.bot_level].label if game.bot_level else "?"
        bot_name = f"Stockfish ({level})"
        if game.player_color is PlayerColor.WHITE:
            white, black = player_name, bot_name
        else:
            white, black = bot_name, player_name
    extra = {}
    if game.event:
        extra["Event"] = game.event
    if game.played_date:
        extra["Date"] = game.played_date
    return rules.build_pgn(
        rules.PgnData(
            white=white,
            black=black,
            played_on=game.created_at.date(),
            initial_fen=game.initial_fen,
            ucis=[m.uci for m in loaded.moves],
            result=game.result,
            undo_count=game.undo_count,
            hint_count=game.hint_count,
            extra_headers=extra,
        )
    )


def import_game(repo: GameRepository, parsed: ParsedPgn, user_color: PlayerColor) -> LoadedGame:
    """Store an imported game. "Bot" moves are the opponent's (the side the user did not play)."""
    board = chess.Board(parsed.initial_fen)
    moves: list[Move] = []
    for uci in parsed.ucis:
        mover = board.turn
        moves.append(
            _record(board, chess.Move.from_uci(uci), by_bot=mover != user_color.chess_color)
        )
    outcome = rules.game_outcome(board)
    game = Game(
        source=GameSource.IMPORTED,
        player_color=user_color,
        initial_fen=parsed.initial_fen,
        white_name=parsed.white,
        black_name=parsed.black,
        event=parsed.event,
        played_date=parsed.date,
        result=pgn_result(parsed, board),
        termination=outcome.termination if outcome else None,
        ended_at=utcnow(),
    )
    repo.save(game, moves)
    assert game.id is not None
    return repo.load(game.id)


class GameService:
    """Commands that change a game. The engine is injected."""

    def __init__(self, repo: GameRepository, engine: Engine, settings: Settings) -> None:
        self._repo = repo
        self._engine = engine
        self._settings = settings

    # --- Commands ---------------------------------------------------------

    async def create(
        self,
        color: ColorChoice,
        level: BotLevel,
        allow_undo: bool,
        allow_hint: bool,
        fen: str | None = None,
    ) -> LoadedGame:
        fen = fen.strip() if fen else None  # blank means the standard start
        initial_fen = rules.validate_start_fen(fen) if fen else chess.STARTING_FEN
        if color is ColorChoice.RANDOM:
            player_color = random.choice([PlayerColor.WHITE, PlayerColor.BLACK])
        else:
            player_color = PlayerColor(color.value)
        game = Game(
            player_color=player_color,
            bot_level=level,
            allow_undo=allow_undo,
            allow_hint=allow_hint,
            initial_fen=initial_fen,
        )
        board = chess.Board(game.initial_fen)
        new_moves: list[Move] = []
        if board.turn != player_color.chess_color:  # the bot has the first move
            new_moves.append(await self._bot_move(board, game))
            if (outcome := rules.game_outcome(board)) is not None:
                _finish(game, outcome)

        self._repo.save(game, new_moves)
        assert game.id is not None
        return self._repo.load(game.id)

    async def play(self, game_id: int, uci: str) -> LoadedGame:
        loaded = self._repo.load(game_id)
        game, board = loaded.game, loaded.board
        self._require_ongoing(game)
        if not loaded.is_player_turn:
            raise GameRuleError("No es tu turno.")

        move = rules.parse_move(board, uci)
        new_moves = [_record(board, move, by_bot=False)]
        outcome = rules.game_outcome(board)
        if outcome is None:
            new_moves.append(await self._bot_move(board, game))
            outcome = rules.game_outcome(board)
        if outcome is not None:
            _finish(game, outcome)
        self._repo.save(game, new_moves)
        return self._repo.load(game_id)

    async def hint(self, game_id: int) -> chess.Square:
        loaded = self._repo.load(game_id)
        game = loaded.game
        self._require_ongoing(game)
        if not game.allow_hint:
            raise GameRuleError("Las pistas no están activadas en esta partida.")
        if not loaded.is_player_turn:
            raise GameRuleError("No es tu turno.")
        best = await self._engine.play(
            loaded.board,
            chess.engine.Limit(time=self._settings.hint_time_s),
            rules.FULL_STRENGTH_OPTIONS,
        )
        game.hint_count += 1
        self._repo.save(game)
        return best.from_square

    def undo(self, game_id: int) -> LoadedGame:
        loaded = self._repo.load(game_id)
        game = loaded.game
        self._require_ongoing(game)
        if not game.allow_undo:
            raise GameRuleError("Deshacer no está activado en esta partida.")
        count = rules.plies_to_undo([m.by_bot for m in loaded.moves])
        if count == 0:
            raise GameRuleError("No hay ninguna jugada tuya que deshacer.")
        self._repo.delete_moves(loaded.moves[-count:])
        game.undo_count += 1
        self._repo.save(game)
        return self._repo.load(game_id)

    def resign(self, game_id: int) -> LoadedGame:
        game = self._repo.load(game_id).game
        self._require_ongoing(game)
        _finish(game, rules.resignation_outcome(game.player_color))
        self._repo.save(game)
        return self._repo.load(game_id)

    async def offer_draw(self, game_id: int) -> tuple[DrawDecline | None, LoadedGame]:
        """Offer a draw to the bot. Returns why it was declined, or None if accepted."""
        loaded = self._repo.load(game_id)
        game = loaded.game
        self._require_ongoing(game)
        if rules.draw_too_early(loaded.board, self._settings.draw_min_moves):
            return DrawDecline.TOO_EARLY, loaded
        score = await self._engine.evaluate(
            loaded.board, chess.engine.Limit(time=self._settings.draw_eval_time_s)
        )
        bot_color = not game.player_color.chess_color
        accepted = rules.should_accept_draw(score, bot_color, self._settings.draw_accept_max_cp)
        if not accepted:
            return DrawDecline.POSITION, loaded
        _finish(game, Outcome(result=rules.DRAW, termination=rules.Termination.DRAW_AGREED))
        self._repo.save(game)
        return None, self._repo.load(game_id)

    # --- Internals --------------------------------------------------------

    async def _bot_move(self, board: chess.Board, game: Game) -> Move:
        """Ask the engine for the bot's move, push it onto `board` and return its record."""
        limit, options = rules.bot_search(
            LEVEL_PRESETS[_bot_level(game)], self._settings.bot_movetime_s
        )
        move = await self._engine.play(board, limit, options)
        return _record(board, move, by_bot=True)

    @staticmethod
    def _require_ongoing(game: Game) -> None:
        if game.is_over:
            raise GameRuleError("La partida ya ha terminado.")


def _record(board: chess.Board, move: chess.Move, *, by_bot: bool) -> Move:
    """Push `move` onto `board` and return an (unsaved) Move record. Requires a legal move."""
    ply = len(board.move_stack)  # `board` is always built from the game's initial FEN
    san = board.san(move)
    board.push(move)
    return Move(game_id=0, ply=ply, uci=move.uci(), san=san, fen_after=board.fen(), by_bot=by_bot)


def _bot_level(game: Game) -> BotLevel:
    if game.bot_level is None:
        raise GameRuleError("Las partidas importadas no se pueden jugar.")
    return game.bot_level


def _finish(game: Game, outcome: Outcome) -> None:
    game.result = outcome.result
    game.termination = outcome.termination
    game.ended_at = utcnow()
