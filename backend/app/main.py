import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import games, health
from app.config import Settings, get_settings
from app.db import init_db, make_db_engine
from app.engine.state import EngineState
from app.engine.stockfish import Engine, EngineUnavailableError, StockfishEngine

logger = logging.getLogger(__name__)

# Every backend route lives under this prefix, in dev (Vite proxy) and in production alike.
API_PREFIX = "/api"

EngineFactory = Callable[[Settings], Awaitable[Engine]]


def create_app(
    settings: Settings | None = None,
    engine_factory: EngineFactory = StockfishEngine.start,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_engine = make_db_engine(resolved_settings.database_url)
        init_db(db_engine)
        app.state.settings = resolved_settings
        app.state.db_engine = db_engine
        app.state.game_lock = asyncio.Lock()

        engine_state = EngineState()
        try:
            engine_state.engine = await engine_factory(resolved_settings)
        except EngineUnavailableError as exc:
            # The API still starts; /api/health reports the problem with a 503.
            logger.error("Engine unavailable: %s", exc)
            engine_state.error = str(exc)
        app.state.engine_state = engine_state
        try:
            yield
        finally:
            if engine_state.engine is not None:
                await engine_state.engine.close()
            db_engine.dispose()

    app = FastAPI(title="whyfish", lifespan=lifespan)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(games.router, prefix=API_PREFIX)
    return app


logging.basicConfig(level=logging.INFO)
app = create_app()
