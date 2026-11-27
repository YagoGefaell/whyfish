import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analysis.book import default_book
from app.analysis.queue import AnalysisQueue
from app.analysis.runner import AnalysisService
from app.api import analysis, games, health, sync, why
from app.config import Settings, get_settings
from app.db import init_db, make_db_engine
from app.engine.pool import PoolManager
from app.engine.state import EngineState
from app.engine.stockfish import Engine, EngineUnavailableError, StockfishEngine
from app.sync.service import ClientFactory, SyncService

logger = logging.getLogger(__name__)

# Every backend route lives under this prefix, in dev (Vite proxy) and in production alike.
API_PREFIX = "/api"

EngineFactory = Callable[[Settings], Awaitable[Engine]]


def create_app(
    settings: Settings | None = None,
    engine_factory: EngineFactory = StockfishEngine.start,
    analysis_engine_factory: EngineFactory = StockfishEngine.start_for_analysis,
    sync_client_factory: ClientFactory | None = None,
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

        def engine_name() -> str | None:
            return engine_state.engine.name if engine_state.engine else None

        pools = PoolManager(analysis_engine_factory, resolved_settings)
        app.state.analysis_pools = pools
        analysis_service = AnalysisService(db_engine, resolved_settings, pools, engine_name)
        analysis_service.mark_interrupted()
        app.state.analysis_service = analysis_service
        queue = AnalysisQueue(db_engine, resolved_settings, analysis_service)
        app.state.analysis_queue = queue
        app.state.sync_service = SyncService(
            db_engine, resolved_settings, sync_client_factory, on_imported=queue.wake
        )
        queue.start()
        # The openings book takes ~2 s to build: load it now, in a thread, so the first review
        # does not wait for it (lru_cache keeps it for every later call).
        book_loading = asyncio.create_task(asyncio.to_thread(default_book))
        try:
            yield
        finally:
            await book_loading
            await app.state.sync_service.stop()
            await queue.stop()
            await analysis_service.shutdown()
            await pools.close()
            if engine_state.engine is not None:
                await engine_state.engine.close()
            db_engine.dispose()

    app = FastAPI(title="whyfish", lifespan=lifespan)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(games.router, prefix=API_PREFIX)
    app.include_router(analysis.router, prefix=API_PREFIX)
    app.include_router(why.router, prefix=API_PREFIX)
    app.include_router(sync.router, prefix=API_PREFIX)
    return app


logging.basicConfig(level=logging.INFO)
app = create_app()
