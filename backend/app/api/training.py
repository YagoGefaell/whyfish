"""Training with the user's errors (phase 6c): sessions, exercises and answers."""

import json
from datetime import date
from typing import Annotated, Literal

import chess
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.analysis import Analysis, ExplanationRead, Repo, _reviewed, get_pools
from app.api.deps import get_settings_dep
from app.api.why import TryRead, TryRequest, best_explanation, judge_attempt
from app.config import LEVEL_PRESETS, Settings
from app.engine.pool import PoolManager
from app.models.game import Game, GameSource, Platform
from app.models.training import TrainingSession
from app.play.rules import PlayerColor
from app.training.logic import Filter
from app.training.service import TrainingService, TrainingSettings

router = APIRouter()

PLATFORM = {Platform.LICHESS: "Lichess", Platform.CHESSCOM: "Chess.com"}
PACE = {
    "bullet": "bala",
    "blitz": "blitz",
    "rapid": "rápida",
    "classical": "clásica",
    "correspondence": "correspondencia",
}
PROMPT = {
    "miss": "El rival acaba de cometer un error: ¿cómo lo aprovechas?",
    "error": "Encuentra la mejor jugada",
}


def get_training(request: Request) -> TrainingService:
    service: TrainingService = request.app.state.training
    return service


Training = Annotated[TrainingService, Depends(get_training)]


def _today() -> date:
    return date.today()


class SettingsRead(BaseModel):
    session_size: int
    weak_new: int
    include_bullet: bool


class PositionRead(BaseModel):
    position: int
    item_id: int
    state: Literal["pending", "correct", "wrong"]
    repeat: bool  # a failed exercise coming back at the end of the session


class SessionRead(BaseModel):
    id: int
    daily: bool  # counts for the streak; False = filtered (from a weak point)
    filter: dict[str, str | bool]
    positions: list[PositionRead]
    current: int | None  # first position without an answer; None = finished
    correct: int
    answered: int
    completed: bool
    streak: int
    counts: dict[str, int]  # due, new, learned, and the excluded by reason (decided, ...)

    @classmethod
    def build(cls, s: TrainingSession, streak: int, counts: dict[str, int]) -> "SessionRead":
        ids: list[int] = json.loads(s.items_json)
        results: dict[str, str] = json.loads(s.results_json)
        positions = [
            PositionRead(
                position=i,
                item_id=item_id,
                state="correct"
                if results.get(str(i)) == "correct"
                else "wrong"
                if results.get(str(i)) == "wrong"
                else "pending",
                repeat=ids.index(item_id) != i,
            )
            for i, item_id in enumerate(ids)
        ]
        current = next((p.position for p in positions if p.state == "pending"), None)
        return cls(
            id=s.id or 0,
            daily=s.daily,
            filter=json.loads(s.filter_json),
            positions=positions,
            current=current,
            correct=sum(p.state == "correct" for p in positions),
            answered=sum(p.state != "pending" for p in positions),
            completed=s.completed,
            streak=streak,
            counts=counts,
        )


@router.get("/training/session")
def get_session(
    training: Training,
    error_kind: str | None = None,
    phase: Literal["opening", "middlegame", "endgame"] | None = None,
    low_time: bool | None = None,
) -> SessionRead:
    """Today's daily session, or a session filtered by error kind / phase / low time."""
    today = _today()
    s = training.session(Filter(error_kind, phase, low_time), today)
    return SessionRead.build(s, training.streak(today), training.counts(today))


class ContextRead(BaseModel):
    opponent: str
    origin: str  # "Chess.com", "Lichess", "PGN", "contra el bot"
    pace: str | None  # "rápida", ...
    move_number: int
    color: PlayerColor  # the user's: the board is oriented to it, and it is to move


class ExerciseRead(BaseModel):
    id: int
    kind: Literal["miss", "error"]
    prompt: str
    fen: str
    last_move: str | None  # UCI of the opponent's last move (highlighted for a ✗)
    context: ContextRead
    error_kind: str | None
    phase: str
    low_time: bool | None


def _context(game: Game, board: chess.Board) -> ContextRead:
    color = game.player_color
    if game.source == GameSource.PLAYED:
        label = LEVEL_PRESETS[game.bot_level].label if game.bot_level else "?"
        opponent, origin = f"Stockfish ({label})", "contra el bot"
    else:
        name = game.black_name if color == PlayerColor.WHITE else game.white_name
        elo = game.black_elo if color == PlayerColor.WHITE else game.white_elo
        opponent = f"{name or '?'}{f' ({elo})' if elo else ''}"
        origin = PLATFORM.get(Platform(game.platform), "?") if game.platform else "PGN"
    return ContextRead(
        opponent=opponent,
        origin=origin,
        pace=PACE.get(game.time_class or ""),
        move_number=board.fullmove_number,
        color=color,
    )


@router.get("/training/items/{item_id}")
def get_exercise(item_id: int, training: Training, repo: Repo) -> ExerciseRead:
    """The position and its context, never the solution."""
    item = training.item(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ejercicio no encontrado.")
    loaded = repo.load(item.game_id)
    board = chess.Board(loaded.game.initial_fen)
    for move in loaded.moves[: item.ply]:
        board.push_uci(move.uci)
    kind: Literal["miss", "error"] = "miss" if item.classification == "miss" else "error"
    return ExerciseRead(
        id=item_id,
        kind=kind,
        prompt=PROMPT[kind],
        fen=board.fen(),
        last_move=loaded.moves[item.ply - 1].uci if item.ply > 0 else None,
        context=_context(loaded.game, board),
        error_kind=item.error_kind,
        phase=item.phase,
        low_time=item.low_time,
    )


class AttemptRead(BaseModel):
    result: TryRead
    # What the best move achieved (level 1), shown when right.
    explanation: ExplanationRead | None
    game_id: int
    ply: int
    external_url: str | None  # the original game: shown once solved
    box: int
    due_on: date | None
    learned: bool
    counted: bool  # the first answer here (retries do not count)
    session: SessionRead


@router.post("/training/sessions/{session_id}/positions/{position}/attempt")
async def attempt(
    session_id: int,
    position: int,
    body: TryRequest,
    training: Training,
    service: Analysis,
    repo: Repo,
    pools: Annotated[PoolManager, Depends(get_pools)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AttemptRead:
    s = training.get_session(session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sesión no encontrada.")
    ids: list[int] = json.loads(s.items_json)
    if not 0 <= position < len(ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ejercicio no encontrado.")
    item = training.item(ids[position])
    assert item is not None
    loaded, evals, review = _reviewed(item.game_id, service, repo)
    result = await judge_attempt(
        service, loaded, evals, review, pools, settings, item.ply, body.uci
    )
    today = _today()
    recorded = training.record(session_id, position, result.correct, today)
    explanation = best_explanation(loaded, evals, review, item.ply) if result.correct else None
    return AttemptRead(
        result=result,
        explanation=ExplanationRead.from_explanation(explanation) if explanation else None,
        game_id=item.game_id,
        ply=item.ply,
        external_url=loaded.game.external_url,
        box=recorded.item.box,
        due_on=recorded.item.due_on,
        learned=recorded.item.learned,
        counted=recorded.counted,
        session=SessionRead.build(recorded.session, training.streak(today), training.counts(today)),
    )


@router.get("/training/settings")
def get_training_settings(training: Training) -> SettingsRead:
    s = training.settings()
    return SettingsRead(
        session_size=s.session_size, weak_new=s.weak_new, include_bullet=s.include_bullet
    )


@router.put("/training/settings")
def put_training_settings(body: SettingsRead, training: Training) -> SettingsRead:
    s = training.set_settings(
        TrainingSettings(body.session_size, body.weak_new, body.include_bullet)
    )
    return SettingsRead(
        session_size=s.session_size, weak_new=s.weak_new, include_bullet=s.include_bullet
    )
