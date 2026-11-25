import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.config import Settings, get_settings
from app.engine.state import EngineState
from app.engine.stockfish import Engine, EngineUnavailableError, StockfishEngine

logger = logging.getLogger(__name__)

EngineFactory = Callable[[Settings], Awaitable[Engine]]


def create_app(
    settings: Settings | None = None,
    engine_factory: EngineFactory = StockfishEngine.start,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine_state = EngineState()
        try:
            engine_state.engine = await engine_factory(resolved_settings)
        except EngineUnavailableError as exc:
            # The API still starts; /health reports the problem with a 503.
            logger.error("Engine unavailable: %s", exc)
            engine_state.error = str(exc)
        app.state.engine_state = engine_state
        try:
            yield
        finally:
            if engine_state.engine is not None:
                await engine_state.engine.close()

    app = FastAPI(title="Chess Coach", lifespan=lifespan)
    app.include_router(health.router)
    return app


logging.basicConfig(level=logging.INFO)
app = create_app()
