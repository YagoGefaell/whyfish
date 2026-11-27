"""Training logic (phase 6c), pure: Leitner boxes, which exercises a session gets, streak."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.config import TRAINING, TrainingThresholds


@dataclass(frozen=True)
class Box:
    box: int
    due_on: date | None
    learned: bool


def after_attempt(box: int, correct: bool, today: date, t: TrainingThresholds = TRAINING) -> Box:
    """Right: one box up (a new exercise goes straight to box 2) and back after that box's
    interval; right in the last box: learned. Wrong: box 1, back tomorrow."""
    last = len(t.intervals)
    if not correct:
        return Box(1, today + timedelta(days=t.intervals[0]), False)
    if box >= last:
        return Box(last, None, True)
    new = min(last, max(1, box) + 1)
    return Box(new, today + timedelta(days=t.intervals[new - 1]), False)


@dataclass(frozen=True)
class Candidate:
    id: int
    box: int
    due_on: date | None
    learned: bool
    excluded: str | None
    error_kind: str | None
    phase: str
    low_time: bool | None
    time_class: str | None
    played_at: datetime
    real: bool = True  # a real game (Lichess, Chess.com, PGN); False = against the bot


@dataclass(frozen=True)
class Filter:
    """A filtered session (from a weak point of the statistics). Empty = the daily session."""

    error_kind: str | None = None
    phase: str | None = None
    low_time: bool | None = None

    @property
    def empty(self) -> bool:
        return self.error_kind is None and self.phase is None and self.low_time is None

    def accepts(self, c: Candidate) -> bool:
        return (
            (self.error_kind is None or c.error_kind == self.error_kind)
            and (self.phase is None or c.phase == self.phase)
            and (self.low_time is None or c.low_time == self.low_time)
        )


def pick_session(
    candidates: Iterable[Candidate],
    today: date,
    size: int,
    weak_kinds: Sequence[str],
    weak_new: int,
    flt: Filter,
    include_bullet: bool,
    include_bot: bool = True,
) -> list[int]:
    """Real games first: their exercises due today (oldest due first), then their new ones
    (in the daily session up to `weak_new` from the weak points' error kinds, the rest the
    most recent errors). Exercises of games against the bot only fill the slots left, in the
    same order, and only with `include_bot`."""
    eligible = [
        c
        for c in candidates
        if c.excluded is None
        and not c.learned
        and (include_bullet or c.time_class != "bullet")
        and (include_bot or c.real)
        and flt.accepts(c)
    ]
    chosen: list[int] = []
    weak_left = weak_new if flt.empty else 0
    for real in (True, False):
        group = [c for c in eligible if c.real == real]
        due = sorted(
            (c for c in group if c.box > 0 and c.due_on is not None and c.due_on <= today),
            key=lambda c: (c.due_on, c.box, c.id),
        )
        chosen += [c.id for c in due[: size - len(chosen)]]
        slots = size - len(chosen)
        if slots <= 0:
            break
        fresh = sorted((c for c in group if c.box == 0), key=lambda c: (c.played_at, c.id))
        fresh.reverse()  # most recent first
        weak = [c for c in fresh if c.error_kind in weak_kinds][: min(weak_left, slots)]
        weak_left -= len(weak)
        rest = [c for c in fresh if c not in weak]
        chosen += [c.id for c in weak + rest[: slots - len(weak)]]
        if len(chosen) >= size:
            break
    return chosen


def streak(completed_days: Iterable[date], today: date) -> int:
    """Consecutive days with the daily session completed, up to today (or yesterday, if
    today's is not done yet)."""
    days = set(completed_days)
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count
