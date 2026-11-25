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


@asynccontextmanager
async def open_pool(
    factory: EngineFactory, settings: Settings, size: int
) -> AsyncIterator[EnginePool]:
    """Start `size` engines (closing any that started if one fails) and close them on exit."""
    results = await asyncio.gather(
        *(factory(settings) for _ in range(size)), return_exceptions=True
    )
    engines = [r for r in results if not isinstance(r, BaseException)]
    errors = [r for r in results if isinstance(r, BaseException)]
    pool = EnginePool(engines)
    if errors:
        await pool.close()
        raise errors[0]
    try:
        yield pool
    finally:
        await pool.close()
