"""Online accounts, synchronisation and the background analysis queue (phase 6a)."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.analysis.queue import AnalysisQueue, QueueStatus
from app.api.deps import get_settings_dep
from app.config import Settings
from app.models.game import Platform
from app.models.sync import ImportAccount
from app.sync.service import SyncService, SyncState

router = APIRouter()


def get_sync(request: Request) -> SyncService:
    service: SyncService = request.app.state.sync_service
    return service


def get_queue(request: Request) -> AnalysisQueue:
    queue: AnalysisQueue = request.app.state.analysis_queue
    return queue


Sync = Annotated[SyncService, Depends(get_sync)]
Queue = Annotated[AnalysisQueue, Depends(get_queue)]


class AccountRead(BaseModel):
    platform: Literal["lichess", "chesscom"]
    username: str
    covered_from: datetime | None  # games from here to `newest_at` are imported
    newest_at: datetime | None
    last_synced_at: datetime | None
    last_error: str | None
    imported_count: int

    @classmethod
    def from_account(cls, a: ImportAccount) -> "AccountRead":
        return cls(
            platform="lichess" if a.platform == Platform.LICHESS else "chesscom",
            username=a.username,
            covered_from=a.covered_from,
            newest_at=a.newest_at,
            last_synced_at=a.last_synced_at,
            last_error=a.last_error,
            imported_count=a.imported_count,
        )


class AccountsRead(BaseModel):
    accounts: list[AccountRead]
    sync_months: int  # how far back the first sync (and each "older games" step) goes


class AccountsUpdate(BaseModel):
    """Usernames; blank or null removes the account."""

    lichess: str | None = None
    chesscom: str | None = None


def _accounts(sync: SyncService, settings: Settings) -> AccountsRead:
    return AccountsRead(
        accounts=[AccountRead.from_account(a) for a in sync.accounts()],
        sync_months=settings.sync_months,
    )


@router.get("/accounts")
def get_accounts(
    sync: Sync, settings: Annotated[Settings, Depends(get_settings_dep)]
) -> AccountsRead:
    return _accounts(sync, settings)


@router.put("/accounts")
def put_accounts(
    body: AccountsUpdate, sync: Sync, settings: Annotated[Settings, Depends(get_settings_dep)]
) -> AccountsRead:
    if sync.state.running:
        raise HTTPException(status.HTTP_409_CONFLICT, "Espera a que termine la sincronización.")
    sync.set_account(Platform.LICHESS, body.lichess)
    sync.set_account(Platform.CHESSCOM, body.chesscom)
    return _accounts(sync, settings)


class AccountProgressRead(BaseModel):
    platform: str
    username: str
    state: Literal["waiting", "running", "done", "error"]
    imported: int
    skipped: int
    error: str | None


class SyncRead(BaseModel):
    running: bool
    older: bool
    accounts: list[AccountProgressRead]
    finished_at: datetime | None

    @classmethod
    def from_state(cls, s: SyncState) -> "SyncRead":
        return cls(
            running=s.running,
            older=s.older,
            accounts=[
                AccountProgressRead(
                    platform=a.platform,
                    username=a.username,
                    state=a.state,
                    imported=a.imported,
                    skipped=a.skipped,
                    error=a.error,
                )
                for a in s.accounts
            ],
            finished_at=s.finished_at,
        )


class SyncStart(BaseModel):
    older: bool = False  # "Importar partidas más antiguas": extend the range back


@router.get("/sync")
def get_sync_state(sync: Sync) -> SyncRead:
    return SyncRead.from_state(sync.state)


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def start_sync(body: SyncStart, sync: Sync) -> SyncRead:
    # async: the sync is scheduled on the running event loop.
    if not sync.accounts():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Configura tus cuentas de Lichess o Chess.com en Ajustes."
        )
    sync.start(older=body.older)  # already running: report its progress
    return SyncRead.from_state(sync.state)


class QueueRead(BaseModel):
    enabled: bool
    paused: bool
    pending: int
    current_game_id: int | None
    failed: int

    @classmethod
    def from_status(cls, q: QueueStatus) -> "QueueRead":
        return cls(
            enabled=q.enabled,
            paused=q.paused,
            pending=q.pending,
            current_game_id=q.current_game_id,
            failed=q.failed,
        )


@router.get("/queue")
def get_queue_status(queue: Queue) -> QueueRead:
    return QueueRead.from_status(queue.status())


@router.post("/queue/pause")
def pause_queue(queue: Queue) -> QueueRead:
    queue.set_paused(True)
    return QueueRead.from_status(queue.status())


@router.post("/queue/resume")
def resume_queue(queue: Queue) -> QueueRead:
    queue.set_paused(False)
    return QueueRead.from_status(queue.status())
