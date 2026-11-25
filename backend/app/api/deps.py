import asyncio
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import Engine as DbEngine
from sqlmodel import Session

from app.config import Settings
from app.engine.state import EngineState
from app.engine.stockfish import Engine
from app.play.service import GameRepository, GameService


def get_engine_state(request: Request) -> EngineState:
    state: EngineState = request.app.state.engine_state
    return state


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    db_engine: DbEngine = request.app.state.db_engine
    with Session(db_engine) as session:
        yield session


def get_engine(engine_state: Annotated[EngineState, Depends(get_engine_state)]) -> Engine:
    if engine_state.engine is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"El motor no está disponible: {engine_state.error}",
        )
    return engine_state.engine


def get_game_repository(session: Annotated[Session, Depends(get_session)]) -> GameRepository:
    return GameRepository(session)


def get_game_service(
    repo: Annotated[GameRepository, Depends(get_game_repository)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> GameService:
    return GameService(repo, engine, settings)


def get_game_lock(request: Request) -> asyncio.Lock:
    """Serializes game mutations (single-user app: one global lock is enough)."""
    lock: asyncio.Lock = request.app.state.game_lock
    return lock
