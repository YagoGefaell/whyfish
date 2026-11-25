"""A pool of engines for analysis, separate from the play engine."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from app.config import Settings
from app.engine.stockfish import Engine

EngineFactory = Callable[[Settings], Awaitable[Engine]]


class EnginePool:
    def __init__(self, engines: list[Engine]) -> None:
        self._engines = engines
        self._idle: asyncio.Queue[Engine] = asyncio.Queue()
        for engine in engines:
            self._idle.put_nowait(engine)

    @property
    def size(self) -> int:
        return len(self._engines)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Engine]:
        engine = await self._idle.get()
        try:
            yield engine
        finally:
            self._idle.put_nowait(engine)

    async def close(self) -> None:
        await asyncio.gather(*(e.close() for e in self._engines), return_exceptions=True)


async def start_pool(factory: EngineFactory, settings: Settings, size: int) -> EnginePool:
    """Start `size` engines; if one fails, close the others and re-raise."""
    results = await asyncio.gather(
        *(factory(settings) for _ in range(size)), return_exceptions=True
    )
    engines = [r for r in results if not isinstance(r, BaseException)]
    errors = [r for r in results if isinstance(r, BaseException)]
    pool = EnginePool(engines)
    if errors:
        await pool.close()
        raise errors[0]
    return pool


class PoolManager:
    """Shared analysis pool: started on first use, closed after `idle_s` without users.

    Used by background analyses and on-demand evaluations. Requests queue for a free engine.
    """

    def __init__(self, factory: EngineFactory, settings: Settings) -> None:
        self._factory = factory
        self._settings = settings
        self._pool: EnginePool | None = None
        self._users = 0
        self._lock = asyncio.Lock()
        self._idle_close: asyncio.TimerHandle | None = None
        self._closing: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def use(self) -> AsyncIterator[EnginePool]:
        async with self._lock:
            if self._idle_close is not None:
                self._idle_close.cancel()
                self._idle_close = None
            if self._closing is not None:
                await self._closing
                self._closing = None
            if self._pool is None:
                size = max(1, self._settings.engine_pool_size)
                self._pool = await start_pool(self._factory, self._settings, size)
            self._users += 1
            pool = self._pool
        try:
            yield pool
        finally:
            self._users -= 1
            if self._users == 0:
                loop = asyncio.get_running_loop()
                self._idle_close = loop.call_later(
                    self._settings.analysis_pool_idle_s, self._close_idle
                )

    def _close_idle(self) -> None:
        if self._users == 0 and self._pool is not None:
            pool, self._pool = self._pool, None
            self._closing = asyncio.get_running_loop().create_task(pool.close())

    async def close(self) -> None:
        if self._idle_close is not None:
            self._idle_close.cancel()
        if self._closing is not None:
            await self._closing
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


@asynccontextmanager
async def open_pool(
    factory: EngineFactory, settings: Settings, size: int
) -> AsyncIterator[EnginePool]:
    """A pool for one-off use (CLI): started here and closed on exit."""
    pool = await start_pool(factory, settings, size)
    try:
        yield pool
    finally:
        await pool.close()
