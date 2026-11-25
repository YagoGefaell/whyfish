"""Helpers for the real-engine classification fixtures (used by the integration test)."""

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import chess.engine
import chess.pgn

from app.analysis.book import default_book
from app.analysis.classify import MoveInput, MoveVerdict, classify
from app.analysis.positions import game_positions
from app.analysis.types import Classification, PositionEval
from app.config import Settings
from app.engine.stockfish import StockfishEngine

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
GAMES_DIR = FIXTURES_DIR / "games"
REAL_FIXTURES = FIXTURES_DIR / "classification" / "real_positions.json"
# Fixed depth, one thread, MultiPV 3: reproducible for a given Stockfish build.
FIXTURE_DEPTH = 20
FIXTURE_MULTIPV = 3


@dataclass(frozen=True)
class Fixture:
    id: str
    pgn: str
    ply: int
    expected: Classification
    source: dict[str, Any]
    note: str
    disputed: str | None  # pending rule decision: runs as xfail


def load_fixtures() -> list[Fixture]:
    data = json.loads(REAL_FIXTURES.read_text(encoding="utf-8"))
    return [
        Fixture(
            f["id"],
            f["pgn"],
            f["ply"],
            Classification(f["expected"]),
            f["source"],
            f["note"],
            f.get("disputed"),
        )
        for f in data["fixtures"]
    ]


def load_game(name: str) -> tuple[str, list[str]]:
    game = chess.pgn.read_game(io.StringIO((GAMES_DIR / name).read_text(encoding="utf-8")))
    assert game is not None
    return game.board().fen(), [m.uci() for m in game.mainline_moves()]


async def classify_fixture(engine: StockfishEngine, fixture: Fixture) -> MoveVerdict:
    initial_fen, ucis = load_game(fixture.pgn)
    ucis = ucis[: fixture.ply + 1]
    positions = game_positions(initial_fen, ucis)
    limit = chess.engine.Limit(depth=FIXTURE_DEPTH)
    book = default_book()

    async def evaluation(index: int) -> PositionEval:
        p = positions[index]
        if p.terminal is not None:
            return p.terminal
        return PositionEval(lines=await engine.analyse(p.board, limit, FIXTURE_MULTIPV))

    def move_input(
        ply: int, before: PositionEval, after: PositionEval, previous: Classification | None
    ) -> MoveInput:
        board = chess.Board(initial_fen)
        for uci in ucis[:ply]:
            board.push_uci(uci)
        after_board = board.copy()
        after_board.push_uci(ucis[ply])
        return MoveInput(
            board,
            chess.Move.from_uci(ucis[ply]),
            before,
            after,
            book.contains(after_board),
            previous,
        )

    previous: Classification | None = None
    current = await evaluation(fixture.ply)
    if fixture.ply > 0:
        prior = await evaluation(fixture.ply - 1)
        previous = classify(move_input(fixture.ply - 1, prior, current, None)).classification
    after = await evaluation(fixture.ply + 1)
    return classify(move_input(fixture.ply, current, after, previous))


async def start_engine(settings: Settings) -> StockfishEngine:
    return await StockfishEngine._start(settings, threads=1, hash_mb=64)
