"""Move marks `[[SAN]]` in explanations: building them with their references and validating them.

Every mark refers to a move of a line in the facts. The reference says where to show it on the
board: the game position the line starts from (`base_ply`) and the moves (UCI) from there up to
and including the marked one.
"""

import re
from dataclasses import dataclass

from app.analysis.detectors.lines import LineOutcome
from app.analysis.facts import MoveFacts

MARK = re.compile(r"\[\[([^\[\]]+)\]\]")


@dataclass(frozen=True)
class MoveRef:
    san: str
    line: str  # "played" | "best" | "second"
    base_ply: int  # game position the path starts from (position before the analysed move)
    path: tuple[str, ...]  # UCI moves from base_ply up to and including this one


def extract_marks(text: str) -> list[str]:
    return MARK.findall(text)


def fact_lines(facts: MoveFacts) -> list[LineOutcome]:
    lines = (facts.played_line, facts.best_line, facts.second_line, facts.sacrifice_line)
    return [ln for ln in lines if ln]


def find_ref(facts: MoveFacts, san: str) -> MoveRef | None:
    """First occurrence of `san` in the facts' lines (played, best, second)."""
    for line in fact_lines(facts):
        for index, candidate in enumerate(line.sans):
            if candidate == san:
                return MoveRef(san, line.name, line.base_ply, line.ucis[: index + 1])
    return None


def invalid_marks(text: str, facts: MoveFacts) -> list[str]:
    """Marks that are not moves of the facts' lines (e.g. a future AI inventing a move)."""
    return [san for san in extract_marks(text) if find_ref(facts, san) is None]


class MarkedText:
    """Collects a text with marks and the exact reference of each mark, in text order.

    Templates know which line a move comes from, so they reference it directly instead of
    searching (the same SAN can appear in two lines with different meanings).
    """

    _TOKEN = "\x00{}\x00"

    def __init__(self) -> None:
        self._refs: dict[str, MoveRef] = {}

    def move(self, line: LineOutcome, index: int) -> str:
        token = self._TOKEN.format(len(self._refs))
        self._refs[token] = MoveRef(
            line.sans[index], line.name, line.base_ply, line.ucis[: index + 1]
        )
        return token

    def moves(self, line: LineOutcome, start: int, stop: int) -> list[str]:
        return [self.move(line, i) for i in range(start, min(stop, len(line.sans)))]

    def render(self, text: str) -> tuple[str, tuple[MoveRef, ...]]:
        refs: list[MoveRef] = []

        def replace(match: re.Match[str]) -> str:
            ref = self._refs[match.group(0)]
            refs.append(ref)
            return f"[[{ref.san}]]"

        rendered = re.sub("\x00\\d+\x00", replace, text)
        return rendered, tuple(refs)
