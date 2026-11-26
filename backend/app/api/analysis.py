from collections.abc import AsyncIterable
from typing import Annotated, Literal

import chess
import chess.engine
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from app.analysis.book import default_book
from app.analysis.evaluate import Evaluation, EvaluationInputError, build_board, evaluate
from app.analysis.review import GameReview, MoveReview, PlayerSummary, build_review
from app.analysis.runner import (
    AnalysisEngineUnavailableError,
    AnalysisNotReadyError,
    AnalysisService,
)
from app.analysis.types import SYMBOLS, Classification, PositionEval
from app.api.deps import get_game_repository, get_settings_dep
from app.config import Settings
from app.engine.pool import PoolManager
from app.engine.stockfish import EngineUnavailableError
from app.explain.idea import Annotation
from app.explain.marks import MoveRef
from app.explain.service import Explanation, explain, facts_for_ply
from app.models.analysis import AnalysisJob, AnalysisStatus
from app.play.rules import PlayerColor
from app.play.service import GameNotFoundError, GameRepository, GameRuleError, LoadedGame

router = APIRouter()

# Seconds between SSE keep-alive comments while nothing changes.
SSE_KEEPALIVE_S = 15.0


def get_analysis_service(request: Request) -> AnalysisService:
    service: AnalysisService = request.app.state.analysis_service
    return service


Analysis = Annotated[AnalysisService, Depends(get_analysis_service)]
Repo = Annotated[GameRepository, Depends(get_game_repository)]


class AnalysisJobRead(BaseModel):
    game_id: int
    status: AnalysisStatus
    done: int
    total: int
    error: str | None

    @classmethod
    def from_job(cls, job: AnalysisJob) -> "AnalysisJobRead":
        return cls(
            game_id=job.game_id, status=job.status, done=job.done, total=job.total, error=job.error
        )


def _color(color: chess.Color) -> PlayerColor:
    return PlayerColor.WHITE if color == chess.WHITE else PlayerColor.BLACK


class MoveReviewRead(BaseModel):
    ply: int
    color: PlayerColor
    uci: str
    san: str
    classification: Classification
    symbol: str
    win_before: float
    win_after: float
    delta: float
    accuracy: float
    best_uci: str | None
    best_san: str | None
    best_line: list[str]
    played_line: list[str]

    @classmethod
    def from_review(cls, m: MoveReview) -> "MoveReviewRead":
        return cls(
            ply=m.ply,
            color=_color(m.color),
            uci=m.uci,
            san=m.san,
            classification=m.classification,
            symbol=SYMBOLS[m.classification],
            win_before=round(m.win_before, 1),
            win_after=round(m.win_after, 1),
            delta=round(m.delta, 1),
            accuracy=round(m.accuracy, 1),
            best_uci=m.best_uci,
            best_san=m.best_san,
            best_line=list(m.best_line),
            played_line=list(m.played_line),
        )


class PlayerSummaryRead(BaseModel):
    accuracy: float | None
    counts: dict[Classification, int]

    @classmethod
    def from_summary(cls, s: PlayerSummary) -> "PlayerSummaryRead":
        accuracy = round(s.accuracy, 1) if s.accuracy is not None else None
        return cls(accuracy=accuracy, counts=s.counts)


class EvalRead(BaseModel):
    """Evaluation of a position from white's point of view."""

    win: float
    cp: int | None
    mate: int | None


class OpeningRead(BaseModel):
    eco: str
    name: str


class ReviewRead(BaseModel):
    game_id: int
    perspective: PlayerColor
    opening: OpeningRead | None
    white: PlayerSummaryRead
    black: PlayerSummaryRead
    key_moments: list[int]
    moves: list[MoveReviewRead]
    evals: list[EvalRead]  # one per position: start + after each move

    @classmethod
    def from_review(cls, game_id: int, perspective: PlayerColor, r: GameReview) -> "ReviewRead":
        return cls(
            game_id=game_id,
            perspective=perspective,
            opening=OpeningRead(eco=r.opening.eco, name=r.opening.name) if r.opening else None,
            white=PlayerSummaryRead.from_summary(r.white),
            black=PlayerSummaryRead.from_summary(r.black),
            key_moments=r.key_moments,
            moves=[MoveReviewRead.from_review(m) for m in r.moves],
            evals=[EvalRead(win=round(e.win, 1), cp=e.cp, mate=e.mate) for e in r.evals],
        )


class EvaluateRequest(BaseModel):
    """Evaluate the position reached from `fen` after `moves` (UCI). Also a coach tool."""

    fen: str = chess.STARTING_FEN
    moves: list[str] = []
    multipv: int = 1


class EvaluatedLineRead(BaseModel):
    uci: list[str]
    san: list[str]
    cp: int | None  # side to move's point of view
    mate: int | None
    win: float


class EvaluationRead(BaseModel):
    fen: str
    turn: PlayerColor
    terminal: Literal["checkmate", "stalemate", "draw"] | None
    lines: list[EvaluatedLineRead]  # best first
    best_uci: str | None
    best_san: str | None
    white: EvalRead  # for the eval bar

    @classmethod
    def from_evaluation(cls, e: Evaluation) -> "EvaluationRead":
        lines = [
            EvaluatedLineRead(
                uci=list(ln.uci), san=list(ln.san), cp=ln.cp, mate=ln.mate, win=round(ln.win, 1)
            )
            for ln in e.lines
        ]
        best = lines[0] if lines else None
        return cls(
            fen=e.fen,
            turn=_color(e.turn),
            terminal=e.terminal,
            lines=lines,
            best_uci=best.uci[0] if best and best.uci else None,
            best_san=best.san[0] if best and best.san else None,
            white=EvalRead(win=round(e.white_win, 1), cp=e.white_cp, mate=e.white_mate),
        )


def get_pools(request: Request) -> PoolManager:
    pools: PoolManager = request.app.state.analysis_pools
    return pools


@router.post("/analysis/evaluate")
async def evaluate_position(
    body: EvaluateRequest,
    pools: Annotated[PoolManager, Depends(get_pools)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> EvaluationRead:
    try:
        board = build_board(body.fen, body.moves)
    except EvaluationInputError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    multipv = max(1, min(body.multipv, settings.evaluate_max_multipv))
    limit = chess.engine.Limit(time=settings.evaluate_time_s)
    try:
        result = await evaluate(pools, board, limit, multipv, settings.evaluate_line_plies)
    except EngineUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return EvaluationRead.from_evaluation(result)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Partida no encontrada.")


@router.post("/games/{game_id}/analysis", status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(game_id: int, service: Analysis, response: Response) -> AnalysisJobRead:
    # async: the job is scheduled with asyncio.create_task on the running event loop.
    try:
        job = service.start(game_id)
    except GameNotFoundError as exc:
        raise _not_found() from exc
    except GameRuleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AnalysisEngineUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if job.status is AnalysisStatus.DONE:
        response.status_code = status.HTTP_200_OK
    return AnalysisJobRead.from_job(job)


@router.get("/games/{game_id}/analysis")
def get_analysis(game_id: int, service: Analysis) -> AnalysisJobRead:
    job = service.job(game_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La partida no se ha analizado.")
    return AnalysisJobRead.from_job(job)


def require_job(game_id: int, service: Analysis) -> int:
    """404 before the stream starts (an exception inside the generator would be too late)."""
    if service.job(game_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La partida no se ha analizado.")
    return game_id


@router.get("/games/{game_id}/analysis/stream", response_class=EventSourceResponse)
async def stream_analysis(
    game_id: Annotated[int, Depends(require_job)], service: Analysis
) -> AsyncIterable[ServerSentEvent]:
    """Progress events until the analysis finishes: `progress`, then `done` or `failed`."""
    last: tuple[str, int, int] | None = None
    while True:
        job = service.job(game_id)
        assert job is not None
        current = (job.status.value, job.done, job.total)
        if current == last:
            yield ServerSentEvent(comment="keep-alive")
        else:
            last = current
            event: Literal["progress", "done", "failed"] = "progress"
            if job.status is AnalysisStatus.DONE:
                event = "done"
            elif job.status is AnalysisStatus.FAILED:
                event = "failed"
            yield ServerSentEvent(data=AnalysisJobRead.from_job(job), event=event)
            if event != "progress":
                return
        await service.wait_for_change(SSE_KEEPALIVE_S)


def _reviewed(
    game_id: int, service: AnalysisService, repo: GameRepository
) -> tuple[LoadedGame, list[PositionEval], GameReview]:
    try:
        loaded = repo.load(game_id)
        _, evals = service.evaluations(game_id)
    except GameNotFoundError as exc:
        raise _not_found() from exc
    except AnalysisNotReadyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    review = build_review(
        loaded.game.initial_fen,
        [m.uci for m in loaded.moves],
        evals,
        perspective=loaded.game.player_color.chess_color,
        book=default_book(),
    )
    return loaded, evals, review


@router.get("/games/{game_id}/review")
def get_review(game_id: int, service: Analysis, repo: Repo) -> ReviewRead:
    loaded, _, review = _reviewed(game_id, service, repo)
    return ReviewRead.from_review(game_id, loaded.game.player_color, review)


class MoveRefRead(BaseModel):
    """Where a [[SAN]] mark of the text is shown: `path` (UCI) played from position `base`."""

    san: str
    line: str
    base: int
    path: list[str]

    @classmethod
    def from_ref(cls, r: MoveRef) -> "MoveRefRead":
        return cls(san=r.san, line=r.line, base=r.base_ply, path=list(r.path))


class AnnotationRead(BaseModel):
    """Drawn on the position after the move. threat/danger: red; attack/target: amber."""

    kind: Literal["arrow", "square"]
    role: Literal["threat", "danger", "attack", "target"]
    square: str | None
    from_square: str | None
    to_square: str | None

    @classmethod
    def from_annotation(cls, a: Annotation) -> "AnnotationRead":
        return cls(
            kind=a.kind,
            role=a.role,
            square=a.square,
            from_square=a.from_square,
            to_square=a.to_square,
        )


class ExplanationRead(BaseModel):
    ply: int
    level: Literal[1, 2]
    text: str | None  # moves marked as [[SAN]], one entry of `refs` per mark, in order
    refs: list[MoveRefRead]
    annotations: list[AnnotationRead]
    idea: str | None

    @classmethod
    def from_explanation(cls, e: Explanation) -> "ExplanationRead":
        return cls(
            ply=e.ply,
            level=e.level,
            text=e.text,
            refs=[MoveRefRead.from_ref(r) for r in e.refs],
            annotations=[AnnotationRead.from_annotation(a) for a in e.annotations],
            idea=e.idea,
        )


@router.get("/games/{game_id}/moves/{ply}/explanation")
def get_explanation(
    game_id: int,
    ply: int,
    service: Analysis,
    repo: Repo,
    level: Annotated[int, Query(ge=1, le=2)] = 1,
) -> ExplanationRead:
    loaded, evals, review = _reviewed(game_id, service, repo)
    ucis = [m.uci for m in loaded.moves]
    if not 0 <= ply < len(ucis):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jugada no encontrada.")
    facts = facts_for_ply(loaded.game.initial_fen, ucis, evals, review, ply, default_book())
    you = review.moves[ply].color == loaded.game.player_color.chess_color
    return ExplanationRead.from_explanation(explain(facts, 1 if level == 1 else 2, you))
