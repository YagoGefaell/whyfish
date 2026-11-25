"""Opening book from the lichess-org/chess-openings dataset (CC0).

Every position along every named line counts as "book", so transpositions are recognised.
"""

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chess

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class Opening:
    eco: str
    name: str


@dataclass(frozen=True)
class OpeningBook:
    # EPD -> the most specific opening that reaches it (a line ending exactly there wins).
    positions: dict[str, Opening]

    def lookup(self, board: chess.Board) -> Opening | None:
        return self.positions.get(board.epd())

    def contains(self, board: chess.Board) -> bool:
        return board.epd() in self.positions


def build_book(rows: list[tuple[str, str, str]]) -> OpeningBook:
    """Build from (eco, name, pgn movetext) rows."""
    exact: dict[str, Opening] = {}
    along: dict[str, tuple[int, Opening]] = {}  # EPD -> (line length, opening), shortest wins
    for eco, name, pgn in rows:
        opening = Opening(eco, name)
        board = chess.Board()
        sans = [tok for tok in pgn.split() if not tok.endswith(".")]
        for i, san in enumerate(sans):
            board.push_san(san)
            epd = board.epd()
            if i == len(sans) - 1:
                exact.setdefault(epd, opening)
            elif epd not in along or along[epd][0] > len(sans):
                along[epd] = (len(sans), opening)
    positions = {epd: opening for epd, (_, opening) in along.items()}
    positions.update(exact)
    return OpeningBook(positions)


def load_rows(data_dir: Path = DATA_DIR) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for path in sorted(data_dir.glob("*.tsv")):
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows.extend((r["eco"], r["name"], r["pgn"]) for r in reader)
    return rows


@lru_cache(maxsize=1)
def default_book() -> OpeningBook:
    return build_book(load_rows())
