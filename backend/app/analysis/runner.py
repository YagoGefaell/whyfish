"""Background analysis of finished games: positions -> engine pool -> cache.

`evaluate_positions` is the DB-free core (also used by the CLI). `AnalysisService` owns the
jobs: one runs at a time, progress is published for the SSE endpoint, results go to the
`PositionAnalysis` cache. Reviews are computed on demand from that cache.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence

import chess
import chess.engine
from sqlalchemy import Engine as DbEngine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.analysis.positions import GamePosition, engine_board, game_positions, position_key
from app.analysis.types import EngineLine, PositionEval
from app.config import Settings
from app.engine.pool import BACKGROUND, FOREGROUND, EnginePool, PoolManager
from app.models.analysis import AnalysisJob, AnalysisStatus, PositionAnalysis
from app.models.game import utcnow
from app.play.service import GameRepository, GameRuleError

logger = logging.getLogger(__name__)


def settings_key(engine_name: str, settings: Settings) -> str:
    depth = settings.analysis_depth if settings.analysis_depth is not None else "-"
    return f"{engine_name}|t={settings.analysis_time_s}|d={depth}|mpv={settings.analysis_multipv}"


def search_limit(settings: Settings) -> chess.engine.Limit:
    return chess.engine.Limit(time=settings.analysis_time_s, depth=settings.analysis_depth)


def lines_to_json(lines: Sequence[EngineLine]) -> str:
    return json.dumps([{"moves": list(ln.moves), "cp": ln.cp, "mate": ln.mate} for ln in lines])


def lines_from_json(text: str) -> tuple[EngineLine, ...]:
    return tuple(
        EngineLine(moves=tuple(d["moves"]), cp=d["cp"], mate=d["mate"]) for d in json.loads(text)
    )


async def evaluate_positions(
    positions: Iterable[GamePosition],
    pool: EnginePool,
    limit: chess.engine.Limit,
    multipv: int,
    on_result: Callable[[GamePosition, tuple[EngineLine, ...]], Awaitable[None] | None],
    priority: Callable[[], int] = lambda: FOREGROUND,
    concurrency: int | None = None,
) -> None:
    """Analyse `positions` in parallel with the pool; call `on_result` as each one finishes.

    `priority` is asked for each position (a background analysis may be promoted while it
    runs); `concurrency` caps how many engines it uses at once (the background queue leaves
    some free for interactive use).
    """
    gate = asyncio.Semaphore(concurrency) if concurrency else contextlib.nullcontext()

    async def work(position: GamePosition) -> None:
        async with gate, pool.acquire(priority()) as engine:
            lines = await engine.analyse(position.board, limit, multipv)
        maybe = on_result(position, lines)
        if maybe is not None:
            await maybe

    await asyncio.gather(*(work(p) for p in positions))


class AnalysisNotReadyError(Exception):
    """The game has no finished analysis (user-facing, Spanish)."""


class AnalysisEngineUnavailableError(Exception):
    """No engine to analyse with (user-facing, Spanish)."""


class AnalysisService:
    def __init__(
        self,
        db_engine: DbEngine,
        settings: Settings,
        pools: PoolManager,
        engine_name: Callable[[], str | None],
    ) -> None:
        self._db = db_engine
        self._settings = settings
        self._pools = pools
        self._engine_name = engine_name
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._one_at_a_time = asyncio.Lock()
        self._changed = asyncio.Condition()
        # Games the background queue is analysing / that the user asked for meanwhile.
        self._background: set[int] = set()
        self._promoted: set[int] = set()

    # --- Lifecycle --------------------------------------------------------

    def mark_interrupted(self) -> None:
        """At startup: jobs left pending/running by a previous process will never finish."""
        with Session(self._db) as session:
            stale = session.exec(
                select(AnalysisJob).where(
                    col(AnalysisJob.status).in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
                )
            ).all()
            for job in stale:
                job.status = AnalysisStatus.FAILED
                job.error = "Análisis interrumpido por un reinicio del servidor."
                session.add(job)
            session.commit()

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    # --- Queries ----------------------------------------------------------

    def cached_lines(self, board: chess.Board) -> tuple[EngineLine, ...] | None:
        """Lines of the game analysis for `board` (SPEC §5.4, coherence between analyses):
        the position itself, or the stored line of its parent that starts with the last move
        (then seen from the new side to move). None if the analysis never saw it."""
        name = self._engine_name()
        if name is None:
            return None
        key = settings_key(name, self._settings)
        own = self._stored(board, key)
        if own is not None:
            return own
        if not board.move_stack:
            return None
        parent = board.copy()
        last = parent.pop().uci()
        for line in self._stored(parent, key) or ():
            if line.move == last and len(line.moves) > 1:
                cp = -line.cp if line.cp is not None else None
                mate = -line.mate if line.mate is not None else None
                return (EngineLine(moves=line.moves[1:], cp=cp, mate=mate),)
        return None

    def _stored(self, board: chess.Board, key: str) -> tuple[EngineLine, ...] | None:
        # Matched by position (pieces, side to move, castling, en passant), not by history.
        prefix = " ".join(board.fen().split()[:4]) + " "
        with Session(self._db) as session:
            row = session.exec(
                select(PositionAnalysis).where(
                    PositionAnalysis.settings_key == key,
                    col(PositionAnalysis.fen).startswith(prefix),
                )
            ).first()
        return lines_from_json(row.lines_json) if row is not None else None

    async def extend(
        self,
        board: chess.Board,
        ucis: Sequence[str],
        needs_more: Callable[[chess.Board, Sequence[str]], bool],
        max_plies: int,
    ) -> tuple[str, ...]:
        """`extend_line` with this service's pools, cache and engine."""
        name = self._engine_name()
        if name is None:
            raise AnalysisEngineUnavailableError("El motor no está disponible.")
        return await extend_line(
            board,
            ucis,
            needs_more=needs_more,
            pools=self._pools,
            db=self._db,
            settings=self._settings,
            engine_name=name,
            max_plies=max_plies,
        )

    def job(self, game_id: int) -> AnalysisJob | None:
        with Session(self._db) as session:
            return session.exec(select(AnalysisJob).where(AnalysisJob.game_id == game_id)).first()

    def evaluations(self, game_id: int) -> tuple[AnalysisJob, list[PositionEval]]:
        """Evaluation of every position of an analysed game, from the cache."""
        job = self.job(game_id)
        if job is None or job.status is not AnalysisStatus.DONE:
            raise AnalysisNotReadyError("La partida no está analizada todavía.")
        with Session(self._db) as session:
            loaded = GameRepository(session).load(game_id)
            positions = game_positions(loaded.game.initial_fen, [m.uci for m in loaded.moves])
            rows = session.exec(
                select(PositionAnalysis).where(
                    PositionAnalysis.settings_key == job.settings_key,
                    col(PositionAnalysis.key).in_([p.key for p in positions]),
                )
            ).all()
        cache = {r.key: lines_from_json(r.lines_json) for r in rows}
        evals: list[PositionEval] = []
        for p in positions:
            if p.terminal is not None:
                evals.append(p.terminal)
            elif p.key in cache:
                evals.append(PositionEval(lines=cache[p.key]))
            else:
                raise AnalysisNotReadyError("Faltan posiciones en la caché; vuelve a analizar.")
        return job, evals

    async def wait_for_change(self, max_wait_s: float) -> None:
        """Return when any job's progress changes, or after `max_wait_s`."""
        async with self._changed:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._changed.wait(), max_wait_s)

    # --- Commands ---------------------------------------------------------

    def start(self, game_id: int) -> AnalysisJob:
        """Queue an analysis unless one is running or already done with these settings."""
        with Session(self._db) as session:
            loaded = GameRepository(session).load(game_id)  # raises GameNotFoundError
            if not loaded.game.is_over:
                raise GameRuleError("Solo se pueden analizar partidas terminadas.")
        name = self._engine_name()
        if name is None:
            raise AnalysisEngineUnavailableError("El motor no está disponible.")
        key = settings_key(name, self._settings)

        with Session(self._db) as session:
            job = session.exec(select(AnalysisJob).where(AnalysisJob.game_id == game_id)).first()
            if job is not None:
                busy = job.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING)
                done = job.status is AnalysisStatus.DONE and job.settings_key == key
                if busy and game_id in self._background:
                    self._promoted.add(game_id)  # the user is waiting for it now
                if busy or done:
                    return job
            else:
                job = AnalysisJob(game_id=game_id, settings_key=key, status=AnalysisStatus.PENDING)
            job.settings_key = key
            job.status = AnalysisStatus.PENDING
            job.done = job.total = 0
            job.error = None
            job.finished_at = None
            session.add(job)
            session.commit()
            session.refresh(job)

        self._tasks[game_id] = asyncio.create_task(self._run(game_id, key))
        return job

    async def analyse_background(self, game_id: int) -> bool:
        """Analyse a game for the background queue (lower priority, fewer engines). Returns
        whether it ended DONE. Counts the attempt (a failed game is retried once)."""
        name = self._engine_name()
        if name is None:
            raise AnalysisEngineUnavailableError("El motor no está disponible.")
        key = settings_key(name, self._settings)
        with Session(self._db) as session:
            job = session.exec(select(AnalysisJob).where(AnalysisJob.game_id == game_id)).first()
            if job is None:
                job = AnalysisJob(game_id=game_id, settings_key=key, status=AnalysisStatus.PENDING)
            elif job.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
                return False  # the user started it meanwhile
            job.settings_key = key
            job.status = AnalysisStatus.PENDING
            job.done = job.total = 0
            job.error = None
            job.finished_at = None
            job.attempts += 1
            session.add(job)
            session.commit()
        self._background.add(game_id)
        try:
            await self._analyse(game_id, key, background=True)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Background analysis of game %s failed", game_id)
            await self._update(game_id, status=AnalysisStatus.FAILED, error=f"Error: {exc}")
            return False
        finally:
            self._background.discard(game_id)
            self._promoted.discard(game_id)

    async def _run(self, game_id: int, key: str) -> None:
        try:
            async with self._one_at_a_time:
                await self._analyse(game_id, key)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Analysis of game %s failed", game_id)
            await self._update(game_id, status=AnalysisStatus.FAILED, error=f"Error: {exc}")
        finally:
            self._tasks.pop(game_id, None)

    async def _analyse(self, game_id: int, key: str, background: bool = False) -> None:
        with Session(self._db) as session:
            loaded = GameRepository(session).load(game_id)
            positions = game_positions(loaded.game.initial_fen, [m.uci for m in loaded.moves])
            todo = [p for p in positions if p.terminal is None]
            cached = set(
                session.exec(
                    select(PositionAnalysis.key).where(
                        PositionAnalysis.settings_key == key,
                        col(PositionAnalysis.key).in_([p.key for p in todo]),
                    )
                ).all()
            )
        missing = list({p.key: p for p in todo if p.key not in cached}.values())
        done = len(todo) - len(missing)
        await self._update(game_id, status=AnalysisStatus.RUNNING, done=done, total=len(todo))

        if missing:

            async def save(position: GamePosition, lines: tuple[EngineLine, ...]) -> None:
                nonlocal done
                with Session(self._db) as session:
                    session.add(
                        PositionAnalysis(
                            key=position.key,
                            settings_key=key,
                            fen=position.board.fen(),
                            lines_json=lines_to_json(lines),
                        )
                    )
                    session.commit()
                done += 1
                await self._update(game_id, done=done)

            def priority() -> int:
                promoted = game_id in self._promoted
                return BACKGROUND if background and not promoted else FOREGROUND

            async with self._pools.use() as pool:
                reserved = self._settings.queue_reserved_engines
                await evaluate_positions(
                    missing,
                    pool,
                    search_limit(self._settings),
                    self._settings.analysis_multipv,
                    save,
                    priority=priority,
                    concurrency=max(1, pool.size - reserved) if background else None,
                )
        await self._update(game_id, status=AnalysisStatus.DONE, finished=True)

    async def _update(
        self,
        game_id: int,
        *,
        status: AnalysisStatus | None = None,
        done: int | None = None,
        total: int | None = None,
        error: str | None = None,
        finished: bool = False,
    ) -> None:
        with Session(self._db) as session:
            job = session.exec(select(AnalysisJob).where(AnalysisJob.game_id == game_id)).one()
            if status is not None:
                job.status = status
            if done is not None:
                job.done = done
            if total is not None:
                job.total = total
            if error is not None:
                job.error = error
            if finished or status is AnalysisStatus.FAILED:
                job.finished_at = utcnow()
            session.add(job)
            session.commit()
        async with self._changed:
            self._changed.notify_all()


def extension_key(engine_name: str, settings: Settings) -> str:
    """Cache key of the short searches that extend lines for "Ver por qué"."""
    return f"{engine_name}|why|t={settings.why_extend_time_s}|mpv=1"


async def extend_line(
    board: chess.Board,
    ucis: Sequence[str],
    *,
    needs_more: Callable[[chess.Board, Sequence[str]], bool],
    pools: PoolManager,
    db: DbEngine,
    settings: Settings,
    engine_name: str,
    max_plies: int,
) -> tuple[str, ...]:
    """Extend `ucis` (played from `board`) with the engine while `needs_more` says the line is
    too short, up to `max_plies`. Each search is cached like any position analysis (its own
    settings key), so the same sequence comes back every time."""
    line = list(ucis)
    key = extension_key(engine_name, settings)
    limit = chess.engine.Limit(time=settings.why_extend_time_s)
    while len(line) < max_plies and needs_more(board, line):
        end = board.copy(stack=False)
        for uci in line:
            end.push_uci(uci)
        if end.is_game_over():
            break
        root = engine_board(end)
        pkey = position_key(root)
        with Session(db) as session:
            row = session.exec(
                select(PositionAnalysis).where(
                    PositionAnalysis.key == pkey, PositionAnalysis.settings_key == key
                )
            ).first()
            cached = lines_from_json(row.lines_json) if row is not None else None
        if cached is None:
            async with pools.use() as pool, pool.acquire() as engine:
                cached = await engine.analyse(root, limit, 1)
            with Session(db) as session, contextlib.suppress(IntegrityError):
                # Another request may have cached the same position meanwhile: keep theirs.
                session.add(
                    PositionAnalysis(
                        key=pkey, settings_key=key, fen=end.fen(), lines_json=lines_to_json(cached)
                    )
                )
                session.commit()
        if not cached or not cached[0].moves:
            break
        line.extend(cached[0].moves)
    return tuple(line[:max_plies])
