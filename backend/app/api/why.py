"""Ver por qué (SPEC §5.4): the sequence that leads to a consequence, and "Pruébalo tú"."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Annotated, Literal

import chess
import chess.engine
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.analysis.book import default_book
from app.analysis.classify import MoveInput, classify, equal_moves
from app.analysis.facts import MoveFacts, build_move_facts
from app.analysis.positions import engine_board, terminal_eval
from app.analysis.review import GameReview
from app.analysis.runner import AnalysisEngineUnavailableError, AnalysisService
from app.analysis.types import Classification, PositionEval
from app.api.analysis import Analysis, MoveRefRead, Repo, _reviewed, get_pools
from app.api.deps import get_settings_dep
from app.config import FACTS, Settings
from app.engine.pool import PoolManager
from app.engine.stockfish import EngineUnavailableError
from app.explain.idea import choose_idea
from app.explain.service import Explanation, explain, facts_for_ply
from app.explain.why import Why, build_why, move_label, needs_extension, why_kind, why_line
from app.play.service import LoadedGame

router = APIRouter()

C = Classification
GOOD_ENOUGH = frozenset({C.BEST, C.GREAT, C.BRILLIANT})


class ArrowRead(BaseModel):
    from_square: str
    to_square: str


class WhyStepRead(BaseModel):
    index: int
    label: str
    san: str
    uci: str
    fen: str
    color: Literal["white", "black"]
    caption: str
    defense: bool
    consequence: bool
    arrows: list[ArrowRead]


class WhyRead(BaseModel):
    kind: Literal["refutation", "idea"]
    tone: Literal["bad", "good"]
    base_ply: int
    start_fen: str
    title: str
    alternative: str | None
    steps: list[WhyStepRead]
    consequence_ply: int | None
    summary: str  # moves marked as [[SAN]], one entry of `refs` per mark
    refs: list[MoveRefRead]
    step_ms: int

    @classmethod
    def from_why(cls, w: Why, step_ms: int) -> "WhyRead":
        return cls(
            kind=w.kind,
            tone=w.tone,
            base_ply=w.base_ply,
            start_fen=w.start_fen,
            title=w.title,
            alternative=w.alternative,
            steps=[
                WhyStepRead(
                    index=s.index,
                    label=s.label,
                    san=s.san,
                    uci=s.uci,
                    fen=s.fen,
                    color="white" if s.color == "white" else "black",
                    caption=s.caption,
                    defense=s.defense,
                    consequence=s.consequence,
                    arrows=[
                        ArrowRead(from_square=a.from_square, to_square=a.to_square)
                        for a in s.arrows
                    ],
                )
                for s in w.steps
            ],
            consequence_ply=w.consequence_ply,
            summary=w.summary,
            refs=[MoveRefRead.from_ref(r) for r in w.refs],
            step_ms=step_ms,
        )


async def _extended(
    service: AnalysisService, facts: MoveFacts, ucis: Sequence[str]
) -> tuple[str, ...]:
    """The line, extended with the engine up to its consequence point when it is too short.
    Without an engine the cached line is used as it is."""
    board = chess.Board(facts.fen_before)
    try:
        return await service.extend(board, ucis, needs_extension, FACTS.consequence_max_plies)
    except (AnalysisEngineUnavailableError, EngineUnavailableError):
        return tuple(ucis)


def _game_board(initial_fen: str, ucis: Sequence[str], ply: int) -> chess.Board:
    board = chess.Board(initial_fen)
    for uci in ucis[:ply]:
        board.push_uci(uci)
    return board


def _facts_for(
    board: chess.Board,
    move: chess.Move,
    before: PositionEval,
    after: PositionEval,
    ply: int,
    previous: Classification | None,
) -> MoveFacts:
    """Facts of a move that is not the one played (an attempt, or the solution)."""
    verdict = classify(MoveInput(board, move, before, after, in_book=False, previous=previous))
    return build_move_facts(
        board,
        move,
        before,
        after,
        ply=ply,
        classification=verdict.classification,
        win_before=verdict.win_before,
        win_after=verdict.win_after,
        delta=verdict.delta,
        opening=None,
        after_opponent_error=previous in (C.MISTAKE, C.BLUNDER),
    )


@router.get("/games/{game_id}/moves/{ply}/why")
async def get_why(
    game_id: int,
    ply: int,
    service: Analysis,
    repo: Repo,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    kind: Annotated[Literal["refutation", "idea", "solution"], Query()] = "refutation",
) -> WhyRead:
    """refutation: why a move that is not the best is worse; idea: what a good move does;
    solution: the best move's line (after a failed "Pruébalo tú")."""
    loaded, evals, review = _reviewed(game_id, service, repo)
    ucis = [m.uci for m in loaded.moves]
    if not 0 <= ply < len(ucis):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jugada no encontrada.")
    user = loaded.game.player_color.chess_color
    facts = facts_for_ply(loaded.game.initial_fen, ucis, evals, review, ply, default_book())
    title = None
    if kind == "solution":
        best = evals[ply].lines[0] if evals[ply].lines else None
        if best is None or facts.is_best:
            raise HTTPException(status.HTTP_409_CONFLICT, "No hay otra jugada mejor que mostrar.")
        board = _game_board(loaded.game.initial_fen, ucis, ply)
        previous = review.moves[ply - 1].classification if ply > 0 else None
        facts = _facts_for(
            board, chess.Move.from_uci(best.move), evals[ply], PositionEval(lines=()), ply, previous
        )
        # The solution is the best move's own line, even if it would classify as "!" (whose
        # idea replays the second option instead).
        facts = replace(facts, classification=C.BEST)
        title = f"La solución: {move_label(facts.fen_before, best.move)}"
        effective: Literal["refutation", "idea"] = "idea"
    else:
        effective = kind
        if why_kind(facts.classification) != kind:
            raise HTTPException(status.HTTP_409_CONFLICT, "Esta jugada no tiene esa explicación.")
        if kind == "idea" and facts.classification == C.BEST and choose_idea(facts) is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Esta jugada no tiene esa explicación.")
    line = why_line(facts, effective)
    if line is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay una línea del motor que mostrar.")
    extended = await _extended(service, facts, line.ucis)
    why = build_why(facts, effective, extended, user, title=title)
    return WhyRead.from_why(why, settings.why_step_ms)


class TryRequest(BaseModel):
    uci: str


class TryRead(BaseModel):
    uci: str
    san: str
    classification: Classification
    correct: bool  # as good as the best move (Δ < equal_max_delta: ★, ! or !!)
    also: list[str]  # other moves as good (SAN): "¡Bien visto! También valía [[X]]"
    why: WhyRead | None  # why the attempt fails (None when it is correct)


async def judge_attempt(
    service: AnalysisService,
    loaded: LoadedGame,
    evals: Sequence[PositionEval],
    review: GameReview,
    pools: PoolManager,
    settings: Settings,
    ply: int,
    uci: str,
) -> TryRead:
    """Judge an attempt in the position before move `ply` ("Pruébalo tú", training).

    Fair comparison (SPEC §5.4): an attempt that is one of the stored MultiPV lines keeps its
    stored value; any other is searched together with the stored best move (searchmoves) with
    the same limits as the game analysis, so both scores come from the same search. Any move
    as good as the best (★, !, !!) is right.
    """
    ucis = [m.uci for m in loaded.moves]
    if not 0 <= ply < len(ucis):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jugada no encontrada.")
    board = _game_board(loaded.game.initial_fen, ucis, ply)
    try:
        move = chess.Move.from_uci(uci)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Jugada no válida.") from exc
    if move not in board.legal_moves:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Jugada ilegal.")
    san = board.san(move)
    stored = evals[ply]
    best = stored.lines[0] if stored.lines else None
    before = stored
    after_board = board.copy()
    after_board.push(move)
    known = any(line.move == move.uci() for line in stored.lines)
    after = terminal_eval(after_board) or PositionEval(lines=())
    if not known and best is not None and not after_board.is_game_over():
        limit = chess.engine.Limit(time=settings.analysis_time_s, depth=settings.analysis_depth)
        root = [chess.Move.from_uci(best.move), move]
        try:
            async with pools.use() as pool, pool.acquire() as engine:
                lines = await engine.analyse(engine_board(board), limit, 2, root_moves=root)
                if not any(line.move == move.uci() for line in lines):
                    # The search did not report the attempt: score it on its own, same limit.
                    reply = await engine.analyse(engine_board(after_board), limit, 1)
                    after = PositionEval(lines=reply)
        except EngineUnavailableError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        before = PositionEval(lines=lines)
    previous = review.moves[ply - 1].classification if ply > 0 else None
    facts = _facts_for(board, move, before, after, ply, previous)
    correct = facts.classification in GOOD_ENOUGH
    also: list[str] = []
    if correct:
        candidates = [best.move] if best is not None else []
        candidates += list(equal_moves(stored))
        also = [board.san(chess.Move.from_uci(u)) for u in candidates if u != move.uci()]
    why = None
    if not correct:
        line = why_line(facts, "refutation")
        if line is not None:
            extended = await _extended(service, facts, line.ucis)
            label = move_label(facts.fen_before, move.uci())
            built = build_why(
                facts, "refutation", extended, board.turn, title=f"Por qué falla {label}"
            )
            why = WhyRead.from_why(built, settings.why_step_ms)
    return TryRead(
        uci=move.uci(),
        san=san,
        classification=facts.classification,
        correct=correct,
        also=list(dict.fromkeys(also)),
        why=why,
    )


def best_explanation(
    loaded: LoadedGame, evals: Sequence[PositionEval], review: GameReview, ply: int
) -> Explanation | None:
    """Level-1 explanation of the best move in the position before move `ply` (what it
    achieved), told to the user; None if there is nothing to say."""
    best = evals[ply].lines[0] if evals[ply].lines else None
    if best is None:
        return None
    ucis = [m.uci for m in loaded.moves]
    board = _game_board(loaded.game.initial_fen, ucis, ply)
    previous = review.moves[ply - 1].classification if ply > 0 else None
    facts = _facts_for(
        board, chess.Move.from_uci(best.move), evals[ply], PositionEval(lines=()), ply, previous
    )
    facts = replace(facts, classification=C.BEST)
    explanation = explain(facts, 1, you=True)
    return explanation if explanation.text else None


@router.post("/games/{game_id}/moves/{ply}/try")
async def try_move(
    game_id: int,
    ply: int,
    body: TryRequest,
    service: Analysis,
    repo: Repo,
    pools: Annotated[PoolManager, Depends(get_pools)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> TryRead:
    """ "Pruébalo tú": the user's attempt in the position before move `ply`."""
    loaded, evals, review = _reviewed(game_id, service, repo)
    return await judge_attempt(service, loaded, evals, review, pools, settings, ply, body.uci)
