"""Engines are handed out by priority: interactive requests never wait behind the queue."""

import asyncio

from app.engine.pool import BACKGROUND, FOREGROUND, INTERACTIVE, EnginePool
from tests.conftest import FakeEngine


async def test_interactive_goes_before_queued_background_work() -> None:
    pool = EnginePool([FakeEngine()])
    order: list[str] = []
    release = asyncio.Event()

    async def hold() -> None:
        async with pool.acquire(BACKGROUND):
            await release.wait()

    async def want(name: str, priority: int) -> None:
        async with pool.acquire(priority):
            order.append(name)

    holder = asyncio.create_task(hold())
    await asyncio.sleep(0)
    waiters = [
        asyncio.create_task(want("background", BACKGROUND)),
        asyncio.create_task(want("foreground", FOREGROUND)),
        asyncio.create_task(want("interactive", INTERACTIVE)),
    ]
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(holder, *waiters)
    assert order == ["interactive", "foreground", "background"]


async def test_a_cancelled_waiter_does_not_keep_the_engine() -> None:
    pool = EnginePool([FakeEngine()])
    async with pool.acquire():
        waiter = asyncio.create_task(pool.acquire().__aenter__())
        await asyncio.sleep(0)
        waiter.cancel()
    async with asyncio.timeout(1), pool.acquire():
        pass
