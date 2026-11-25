import asyncio
from typing import Annotated

import chess
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.api.deps import get_game_lock, get_game_repository, get_game_service, get_settings_dep
from app.api.schemas import (
    DrawOfferRead,
    GameCreate,
    GameImport,
    GameImportRead,
    GameState,
    GameSummary,
    HintRead,
    LevelRead,
    MoveCreate,
)
from app.config import LEVEL_PRESETS, Settings
from app.engine.stockfish import EngineUnavailableError
from app.play.pgn import PgnImportError, detect_user_color, parse_pgn
from app.play.rules import IllegalMoveError, InvalidFenError
from app.play.service import (
    GameNotFoundError,
    GameRepository,
    GameRuleError,
    GameService,
    game_pgn,
    import_game,
)

router = APIRouter()

Service = Annotated[GameService, Depends(get_game_service)]
Repo = Annotated[GameRepository, Depends(get_game_repository)]
Lock = Annotated[asyncio.Lock, Depends(get_game_lock)]


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Partida no encontrada.")
    if isinstance(exc, InvalidFenError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if isinstance(exc, IllegalMoveError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, "Jugada ilegal.")
    if isinstance(exc, GameRuleError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, EngineUnavailableError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"El motor ha fallado: {exc}")
    raise exc


_ERRORS = (
    GameNotFoundError,
    InvalidFenError,
    IllegalMoveError,
    GameRuleError,
    EngineUnavailableError,
)


@router.get("/levels")
def list_levels() -> list[LevelRead]:
    return [LevelRead(id=level, label=preset.label) for level, preset in LEVEL_PRESETS.items()]


@router.get("/games")
def list_games(repo: Repo) -> list[GameSummary]:
    statuses = repo.analysis_statuses()
    return [
        GameSummary.from_game(game, count, statuses.get(game.id or 0))
        for game, count in repo.list_with_move_counts()
    ]


@router.post("/games/import", status_code=status.HTTP_201_CREATED)
def import_pgn(
    body: GameImport, repo: Repo, settings: Annotated[Settings, Depends(get_settings_dep)]
) -> GameImportRead:
    try:
        parsed = parse_pgn(body.pgn)
    except PgnImportError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    user_color = body.user_color or detect_user_color(parsed, settings.player_name)
    if user_color is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "color_required",
                "message": "No se pudo deducir qué color jugaste. Indícalo.",
                "white": parsed.white,
                "black": parsed.black,
            },
        )
    warnings = []
    if parsed.games_in_text > 1:
        warnings.append(
            f"El PGN contiene {parsed.games_in_text} partidas; solo se ha importado la primera."
        )
    return GameImportRead(
        game=GameState.from_loaded(import_game(repo, parsed, user_color)), warnings=warnings
    )


@router.post("/games", status_code=status.HTTP_201_CREATED)
async def create_game(body: GameCreate, service: Service, lock: Lock) -> GameState:
    async with lock:
        try:
            loaded = await service.create(
                body.color, body.level, body.allow_undo, body.allow_hint, fen=body.fen
            )
        except _ERRORS as exc:
            raise _http_error(exc) from exc
    return GameState.from_loaded(loaded)


@router.get("/games/{game_id}")
def get_game(game_id: int, repo: Repo) -> GameState:
    try:
        return GameState.from_loaded(repo.load(game_id), repo.analysis_status(game_id))
    except _ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/games/{game_id}/moves")
async def play_move(game_id: int, body: MoveCreate, service: Service, lock: Lock) -> GameState:
    async with lock:
        try:
            return GameState.from_loaded(await service.play(game_id, body.uci))
        except _ERRORS as exc:
            raise _http_error(exc) from exc


@router.post("/games/{game_id}/undo")
async def undo(game_id: int, service: Service, lock: Lock) -> GameState:
    async with lock:
        try:
            return GameState.from_loaded(service.undo(game_id))
        except _ERRORS as exc:
            raise _http_error(exc) from exc


@router.post("/games/{game_id}/hint")
async def hint(game_id: int, service: Service, lock: Lock) -> HintRead:
    async with lock:
        try:
            square = await service.hint(game_id)
        except _ERRORS as exc:
            raise _http_error(exc) from exc
    return HintRead(square=chess.square_name(square))


@router.post("/games/{game_id}/resign")
async def resign(game_id: int, service: Service, lock: Lock) -> GameState:
    async with lock:
        try:
            return GameState.from_loaded(service.resign(game_id))
        except _ERRORS as exc:
            raise _http_error(exc) from exc


@router.post("/games/{game_id}/draw")
async def offer_draw(
    game_id: int,
    service: Service,
    lock: Lock,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> DrawOfferRead:
    async with lock:
        try:
            declined, loaded = await service.offer_draw(game_id)
        except _ERRORS as exc:
            raise _http_error(exc) from exc
    return DrawOfferRead(
        accepted=declined is None,
        declined_reason=declined,
        min_moves=settings.draw_min_moves,
        game=GameState.from_loaded(loaded),
    )


@router.get("/games/{game_id}/pgn", response_class=PlainTextResponse)
def download_pgn(
    game_id: int, repo: Repo, settings: Annotated[Settings, Depends(get_settings_dep)]
) -> PlainTextResponse:
    try:
        pgn = game_pgn(repo.load(game_id), settings.player_name)
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    return PlainTextResponse(
        pgn,
        media_type="application/x-chess-pgn",
        headers={"Content-Disposition": f'attachment; filename="whyfish-{game_id}.pgn"'},
    )
