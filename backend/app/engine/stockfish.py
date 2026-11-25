"""Stockfish wrapper: start, configure, search, healthcheck and clean shutdown."""

import asyncio
import contextlib
import logging
from collections.abc import Mapping
from typing import Protocol

import chess
import chess.engine

from app.analysis.types import EngineLine
from app.config import Settings

logger = logging.getLogger(__name__)

EngineOptions = Mapping[str, str | int | bool]


class EngineUnavailableError(Exception):
    """The engine could not be started, died, or is not responding."""


class Engine(Protocol):
    """Engine interface; injected so tests can use a fake."""

    @property
    def name(self) -> str: ...

    @property
    def is_alive(self) -> bool:
        """Whether the engine process is still running."""

    @property
    def is_busy(self) -> bool:
        """Whether a command (e.g. a search) is currently in progress."""

    async def ping(self) -> None:
        """Raise EngineUnavailableError if the engine does not respond."""

    async def play(
        self, board: chess.Board, limit: chess.engine.Limit, options: EngineOptions
    ) -> chess.Move:
        """Best move under `limit`, with `options` applied only for this search."""

    async def evaluate(
        self, board: chess.Board, limit: chess.engine.Limit
    ) -> chess.engine.PovScore:
        """Full-strength evaluation of `board`."""

    async def analyse(
        self, board: chess.Board, limit: chess.engine.Limit, multipv: int
    ) -> tuple[EngineLine, ...]:
        """Top `multipv` lines (best first), scores from the side to move's point of view.

        `board`'s move history is sent too, so the engine can see repetitions.
        """

    async def close(self) -> None: ...


class StockfishEngine:
    def __init__(
        self,
        transport: asyncio.SubprocessTransport,
        protocol: chess.engine.UciProtocol,
        settings: Settings,
    ) -> None:
        self._transport = transport
        self._protocol = protocol
        self._settings = settings
        # A UCI engine handles one command at a time; python-chess cancels the in-flight
        # command if a second one is sent concurrently. Every command goes through this lock.
        self._lock = asyncio.Lock()

    @classmethod
    async def start(cls, settings: Settings) -> "StockfishEngine":
        """Engine for playing (and hints / draw offers)."""
        return await cls._start(settings, settings.engine_threads, settings.engine_hash_mb)

    @classmethod
    async def start_for_analysis(cls, settings: Settings) -> "StockfishEngine":
        """One engine of the analysis pool."""
        return await cls._start(settings, settings.analysis_threads, settings.analysis_hash_mb)

    @classmethod
    async def _start(cls, settings: Settings, threads: int, hash_mb: int) -> "StockfishEngine":
        path = settings.stockfish_path
        if path is None:
            raise EngineUnavailableError("STOCKFISH_PATH is not configured")
        if not path.is_file():
            raise EngineUnavailableError(f"Stockfish binary not found at {path}")

        try:
            transport, protocol = await asyncio.wait_for(
                chess.engine.popen_uci(str(path)), timeout=settings.engine_start_timeout_s
            )
        except (OSError, TimeoutError, chess.engine.EngineError) as exc:
            raise EngineUnavailableError(f"Could not start Stockfish: {exc!r}") from exc

        engine = cls(transport, protocol, settings)
        try:
            await protocol.configure({"Threads": threads, "Hash": hash_mb})
        except chess.engine.EngineError as exc:
            await engine.close()
            raise EngineUnavailableError(f"Could not configure Stockfish: {exc!r}") from exc

        logger.info("Engine started: %s (%s)", engine.name, path)
        return engine

    @property
    def name(self) -> str:
        return self._protocol.id.get("name", "unknown")

    @property
    def is_alive(self) -> bool:
        return not self._protocol.returncode.done()

    @property
    def is_busy(self) -> bool:
        return self._lock.locked()

    async def ping(self) -> None:
        try:
            await asyncio.wait_for(
                self._locked_ping(), timeout=self._settings.engine_ping_timeout_s
            )
        except (TimeoutError, chess.engine.EngineError) as exc:
            raise EngineUnavailableError(f"Engine not responding: {exc!r}") from exc

    async def _locked_ping(self) -> None:
        async with self._lock:
            await self._protocol.ping()

    async def play(
        self, board: chess.Board, limit: chess.engine.Limit, options: EngineOptions
    ) -> chess.Move:
        try:
            async with self._lock:
                result = await self._protocol.play(board, limit, options=dict(options))
        except chess.engine.EngineError as exc:
            raise EngineUnavailableError(f"Engine failed while searching: {exc!r}") from exc
        if result.move is None:
            raise EngineUnavailableError("Engine returned no move")
        return result.move

    async def evaluate(
        self, board: chess.Board, limit: chess.engine.Limit
    ) -> chess.engine.PovScore:
        try:
            async with self._lock:
                info = await self._protocol.analyse(board, limit)
        except chess.engine.EngineError as exc:
            raise EngineUnavailableError(f"Engine failed while analysing: {exc!r}") from exc
        score = info.get("score")
        if score is None:
            raise EngineUnavailableError("Engine returned no score")
        return score

    async def analyse(
        self, board: chess.Board, limit: chess.engine.Limit, multipv: int
    ) -> tuple[EngineLine, ...]:
        try:
            async with self._lock:
                infos = await self._protocol.analyse(board, limit, multipv=multipv)
        except chess.engine.EngineError as exc:
            raise EngineUnavailableError(f"Engine failed while analysing: {exc!r}") from exc
        lines: list[EngineLine] = []
        for info in infos:
            pv, score = info.get("pv"), info.get("score")
            if not pv or score is None:
                continue
            relative = score.pov(board.turn)
            lines.append(
                EngineLine(
                    moves=tuple(m.uci() for m in pv), cp=relative.score(), mate=relative.mate()
                )
            )
        if not lines:
            raise EngineUnavailableError("Engine returned no lines")
        return tuple(lines)

    async def close(self) -> None:
        # The process may already be dead, e.g. Ctrl-C in `make dev` sends SIGINT to the whole
        # process group, so Stockfish can exit before we get to send `quit`.
        if self._protocol.returncode.done():
            logger.info("Engine already exited (code %s)", self._protocol.returncode.result())
            self._transport.close()
            return
        try:
            await asyncio.wait_for(
                self._protocol.quit(), timeout=self._settings.engine_quit_timeout_s
            )
        # RuntimeError: the pipe was closed between the check above and writing `quit`.
        except (TimeoutError, RuntimeError, chess.engine.EngineError) as exc:
            logger.warning("Engine did not quit cleanly (%r); killing it", exc)
        finally:
            with contextlib.suppress(ProcessLookupError):
                self._transport.close()
        logger.info("Engine stopped")
