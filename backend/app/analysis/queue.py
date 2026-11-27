"""Background analysis queue (phase 6a): synchronised games are analysed one by one.

Most recent game first. A game the user opens is analysed in the foreground (it goes first:
its positions get engines before the queue's). Failed games are retried once. The queue can
be paused (persisted, survives restarts): it stops after the positions being searched and,
when resumed, goes on with the same game from the cache. It leaves `queue_reserved_engines`
engines free.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from sqlalchemy import Engine as DbEngine
from sqlmodel import Session, col, func, select

from app.analysis.runner import AnalysisEngineUnavailableError, AnalysisService
from app.config import Settings
from app.models.analysis import AnalysisJob, AnalysisStatus
from app.models.game import Game
from app.settings_store import QUEUE_PAUSED, get_setting, set_setting

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # the first try and one retry


@dataclass(frozen=True)
class QueueStatus:
    enabled: bool
    paused: bool
    pending: int  # synchronised games still to analyse (including the current one)
    current_game_id: int | None
    failed: int  # given up after the retry


def _waiting(session: Session) -> list[int]:
    """Synchronised games to analyse, most recent first."""
    rows = session.exec(
        select(Game.id, AnalysisJob.status, AnalysisJob.attempts)
        .join(AnalysisJob, col(AnalysisJob.game_id) == col(Game.id), isouter=True)
        .where(col(Game.platform).is_not(None))
        .order_by(col(Game.played_at).desc(), col(Game.id).desc())
    ).all()
    out: list[int] = []
    for game_id, status, attempts in rows:
        if game_id is None or status is AnalysisStatus.DONE:
            continue
        if status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
            continue  # being analysed (foreground or by the queue)
        if status is AnalysisStatus.FAILED and (attempts or 0) >= MAX_ATTEMPTS:
            continue
        out.append(game_id)
    return out


class AnalysisQueue:
    def __init__(self, db: DbEngine, settings: Settings, service: AnalysisService) -> None:
        self._db = db
        self._settings = settings
        self._service = service
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._current: int | None = None
        self._paused: bool | None = None  # in memory once read (checked for every position)
        self._resume: int | None = None  # game interrupted by a pause: next on resume

    # --- Control ------------------------------------------------------------

    def start(self) -> None:
        if self._settings.queue_enabled and self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def wake(self) -> None:
        """New games may be waiting (after a sync, or when resumed)."""
        self._wake.set()

    @property
    def paused(self) -> bool:
        if self._paused is None:
            self._paused = get_setting(self._db, QUEUE_PAUSED, "0") == "1"
        return self._paused

    def set_paused(self, paused: bool) -> None:
        """Pausing stops the current game after the positions being searched; resuming goes on
        with that same game (its finished positions are in the cache)."""
        set_setting(self._db, QUEUE_PAUSED, "1" if paused else "0")
        self._paused = paused
        if not paused:
            self.wake()

    def status(self) -> QueueStatus:
        with Session(self._db) as session:
            waiting = _waiting(session)
            failed = session.exec(
                select(func.count())
                .select_from(AnalysisJob)
                .join(Game, col(Game.id) == col(AnalysisJob.game_id))
                .where(
                    col(Game.platform).is_not(None),
                    AnalysisJob.status == AnalysisStatus.FAILED,
                    col(AnalysisJob.attempts) >= MAX_ATTEMPTS,
                )
            ).one()
        current = self._current
        pending = len(waiting) + (1 if current is not None and current not in waiting else 0)
        return QueueStatus(
            enabled=self._settings.queue_enabled,
            paused=self.paused,
            pending=pending,
            current_game_id=current,
            failed=int(failed),
        )

    # --- Worker ---------------------------------------------------------------

    def next_game(self) -> int | None:
        with Session(self._db) as session:
            waiting = _waiting(session)
        if self._resume is not None and self._resume in waiting:
            return self._resume
        return waiting[0] if waiting else None

    async def _loop(self) -> None:
        while True:
            game_id = None if self.paused else self.next_game()
            if game_id is None:
                self._wake.clear()
                await self._wake.wait()
                continue
            self._current = game_id
            try:
                outcome = await self._service.analyse_background(game_id, lambda: self.paused)
                self._resume = game_id if outcome == "paused" else None
            except AnalysisEngineUnavailableError:
                # No engine: wait for the next sync or resume instead of spinning.
                logger.warning("Analysis queue: no engine available")
                self._current = None
                self._wake.clear()
                await self._wake.wait()
                continue
            finally:
                self._current = None
            if self._settings.queue_pause_between_s > 0:
                await asyncio.sleep(self._settings.queue_pause_between_s)
