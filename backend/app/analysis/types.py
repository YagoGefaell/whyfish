"""Plain data shared by the analysis modules. No logic beyond trivial helpers."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class EngineLine:
    """One MultiPV line. Score is from the point of view of the side to move."""

    moves: tuple[str, ...]  # UCI; moves[0] is the candidate move
    cp: int | None = None
    mate: int | None = None  # > 0: side to move mates in N; < 0: gets mated in N

    @property
    def move(self) -> str:
        return self.moves[0]


@dataclass(frozen=True)
class PositionEval:
    """Engine view of a position: MultiPV lines (best first) or a terminal value.

    `terminal_win` is set for finished positions (mate, stalemate, draws): win% for the side
    to move (0 = checkmated, 50 = draw). Then `lines` is empty.
    """

    lines: tuple[EngineLine, ...] = ()
    terminal_win: float | None = None


class Classification(StrEnum):
    BOOK = "book"
    BRILLIANT = "brilliant"
    GREAT = "great"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"
    MISS = "miss"


SYMBOLS: dict[Classification, str] = {
    Classification.BOOK: "📖",
    Classification.BRILLIANT: "!!",
    Classification.GREAT: "!",
    Classification.BEST: "★",
    Classification.EXCELLENT: "",
    Classification.GOOD: "",
    Classification.INACCURACY: "?!",
    Classification.MISTAKE: "?",
    Classification.BLUNDER: "??",
    Classification.MISS: "✗",
}
