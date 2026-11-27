"""Synchronisation of the user's online games (phase 6a).

- First sync: the last `sync_months` months. Then incremental: only games newer than the
  newest one imported. "Older games" extends the covered range back by `sync_months`.
- Games are read oldest first and stored one by one, so an interrupted sync resumes where it
  stopped; a game is never stored twice (platform + external id).
- The user's colour is the side whose name is the account's username (case-insensitive).
- Network or API errors stop that account's sync and are kept in `last_error`; nothing is
  half stored, and the other account still syncs.
"""

import asyncio
import calendar
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from sqlalchemy import Engine as DbEngine
from sqlmodel import Session, select

from app.config import Settings
from app.models.game import Game, Platform, utcnow
from app.models.sync import ImportAccount
from app.play.pgn import PgnImportError, parse_pgn
from app.play.rules import PlayerColor
from app.play.service import GameRepository, import_game
from app.sync import chesscom, lichess
from app.sync.types import OnlineGame, SyncError

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], httpx.AsyncClient]
Fetch = Callable[
    [httpx.AsyncClient, str, str, datetime | None, datetime | None, float],
    AsyncIterator[OnlineGame],
]


def months_before(moment: datetime, months: int) -> datetime:
    """Same day `months` calendar months earlier (clamped to the month's length)."""
    month_index = moment.year * 12 + moment.month - 1 - months
    year, month = divmod(month_index, 12)
    day = min(moment.day, calendar.monthrange(year, month + 1)[1])
    return moment.replace(year=year, month=month + 1, day=day)


@dataclass
class AccountProgress:
    platform: str
    username: str
    state: str = "waiting"  # waiting | running | done | error
    imported: int = 0
    skipped: int = 0  # already stored, variants, or the user is not one of the players
    error: str | None = None


@dataclass
class SyncState:
    running: bool = False
    older: bool = False  # extending the range back ("Importar partidas más antiguas")
    accounts: list[AccountProgress] = field(default_factory=list)
    finished_at: datetime | None = None


def _user_color(game: OnlineGame, username: str) -> PlayerColor | None:
    wanted = username.casefold()
    if game.white.casefold() == wanted:
        return PlayerColor.WHITE
    if game.black.casefold() == wanted:
        return PlayerColor.BLACK
    return None


class SyncService:
    def __init__(
        self,
        db: DbEngine,
        settings: Settings,
        client_factory: ClientFactory | None = None,
        on_imported: Callable[[], None] = lambda: None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._client_factory = client_factory or self._default_client
        self._on_imported = on_imported
        self._state = SyncState()
        self._task: asyncio.Task[None] | None = None
        self._fetchers: dict[str, tuple[Fetch, str]] = {
            Platform.LICHESS: (lichess.fetch_games, settings.lichess_url),
            Platform.CHESSCOM: (chesscom.fetch_games, settings.chesscom_url),
        }

    def _default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._settings.sync_timeout_s,
            headers={"User-Agent": self._settings.sync_user_agent},
            follow_redirects=True,
        )

    # --- Accounts -------------------------------------------------------------

    def accounts(self) -> list[ImportAccount]:
        with Session(self._db) as session:
            return list(session.exec(select(ImportAccount)).all())

    def set_account(self, platform: str, username: str | None) -> None:
        """Set (or remove, with None/blank) the account of a platform. A different username is
        a new account: its range starts again."""
        name = (username or "").strip()
        with Session(self._db) as session:
            account = session.exec(
                select(ImportAccount).where(ImportAccount.platform == platform)
            ).first()
            if not name:
                if account is not None:
                    session.delete(account)
                    session.commit()
                return
            if account is None or account.username.casefold() != name.casefold():
                if account is not None:
                    session.delete(account)
                    session.flush()
                account = ImportAccount(platform=platform, username=name)
            account.username = name
            session.add(account)
            session.commit()

    # --- Sync -----------------------------------------------------------------

    @property
    def state(self) -> SyncState:
        return self._state

    def start(self, older: bool = False) -> bool:
        """Start a sync in the background; False if one is already running."""
        if self._state.running:
            return False
        accounts = self.accounts()
        self._state = SyncState(
            running=True,
            older=older,
            accounts=[AccountProgress(a.platform, a.username) for a in accounts],
        )
        self._task = asyncio.create_task(self._run(older))
        return True

    async def wait(self) -> None:
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await self.wait()

    async def _run(self, older: bool) -> None:
        try:
            async with self._client_factory() as client:
                for progress in self._state.accounts:
                    await self._sync_account(client, progress, older)
        finally:
            self._state.running = False
            self._state.finished_at = utcnow()

    async def _sync_account(
        self, client: httpx.AsyncClient, progress: AccountProgress, older: bool
    ) -> None:
        progress.state = "running"
        fetch, base_url = self._fetchers[progress.platform]
        with Session(self._db) as session:
            account = session.exec(
                select(ImportAccount).where(ImportAccount.platform == progress.platform)
            ).first()
            if account is None:
                progress.state = "done"
                return
            covered_from, newest_at = account.covered_from, account.newest_at
        now = utcnow()
        months = self._settings.sync_months
        if older:
            until = covered_from or months_before(now, months)
            since: datetime | None = months_before(until, months)
        elif newest_at is not None:
            since, until = newest_at + timedelta(milliseconds=1), None
        else:
            since, until = months_before(now, months), None
        error: str | None = None
        try:
            async for game in fetch(
                client, base_url, progress.username, since, until, self._settings.sync_retry_wait_s
            ):
                if self._store(game, progress.username):
                    progress.imported += 1
                    self._advance(progress.platform, game.played_at, older)
                    self._on_imported()
                else:
                    progress.skipped += 1
        except SyncError as exc:
            error = str(exc)
        except httpx.HTTPError as exc:
            logger.warning("Sync %s failed: %r", progress.platform, exc)
            error = "No se pudo conectar con el servidor. Inténtalo más tarde."
        except ValueError as exc:  # malformed JSON
            logger.warning("Sync %s: bad response: %r", progress.platform, exc)
            error = "La respuesta del servidor no se pudo leer."
        with Session(self._db) as session:
            account = session.exec(
                select(ImportAccount).where(ImportAccount.platform == progress.platform)
            ).first()
            if account is not None:
                account.last_synced_at = utcnow()
                account.last_error = error
                account.imported_count += progress.imported
                # Without errors the whole requested range is covered now.
                widened = since is not None and (
                    account.covered_from is None or since < account.covered_from
                )
                if error is None and widened:
                    account.covered_from = since
                session.add(account)
                session.commit()
        progress.error = error
        progress.state = "error" if error else "done"

    def _advance(self, platform: str, played_at: datetime, older: bool) -> None:
        """Move the newest-game cursor as games are stored (oldest first), so an interrupted
        incremental sync resumes after the last game stored."""
        if older:
            return
        with Session(self._db) as session:
            account = session.exec(
                select(ImportAccount).where(ImportAccount.platform == platform)
            ).first()
            if account is not None and (account.newest_at is None or played_at > account.newest_at):
                account.newest_at = played_at
                session.add(account)
                session.commit()

    def _store(self, game: OnlineGame, username: str) -> bool:
        """Store one game; False if it is already there or cannot be imported."""
        color = _user_color(game, username)
        if color is None:
            return False
        with Session(self._db) as session:
            exists = session.exec(
                select(Game.id).where(
                    Game.platform == game.platform, Game.external_id == game.external_id
                )
            ).first()
            if exists is not None:
                return False
            try:
                parsed = parse_pgn(game.pgn)
            except PgnImportError:
                return False
            import_game(GameRepository(session), parsed, color, game)
        return True
