"""Leitner boxes, session selection and streak (pure)."""

from datetime import UTC, date, datetime, timedelta

from app.training.logic import Candidate, Filter, after_attempt, pick_session, streak
from app.training.service import exclusion

TODAY = date(2026, 11, 27)


def test_leitner_boxes() -> None:
    assert after_attempt(0, True, TODAY) == after_attempt(1, True, TODAY)  # new: straight to 2
    b = after_attempt(0, True, TODAY)
    assert (b.box, b.due_on, b.learned) == (2, TODAY + timedelta(days=2), False)
    assert after_attempt(4, True, TODAY).due_on == TODAY + timedelta(days=16)
    assert after_attempt(5, True, TODAY).learned  # right in the last box: learned
    wrong = after_attempt(4, False, TODAY)
    assert (wrong.box, wrong.due_on) == (1, TODAY + timedelta(days=1))


def c(
    i: int,
    *,
    box: int = 0,
    due: date | None = None,
    kind: str = "positional",
    phase: str = "middlegame",
    tc: str | None = "rapid",
    excluded: str | None = None,
    learned: bool = False,
    low: bool | None = None,
) -> Candidate:
    played = datetime(2026, 11, 1, tzinfo=UTC) + timedelta(days=i)
    return Candidate(i, box, due, learned, excluded, kind, phase, low, tc, played)


def test_due_first_then_weak_kinds_then_most_recent() -> None:
    items = [
        c(1, box=2, due=TODAY - timedelta(days=1)),
        c(2, box=3, due=TODAY + timedelta(days=3)),  # not due yet
        c(3, kind="hanging"),
        c(4, kind="hanging"),
        c(5, kind="missed_gain"),
        c(6),
        c(7),
        c(8),
        c(9, kind="hanging"),
        c(10, excluded="unclear"),
        c(11, learned=True),
        c(12, tc="bullet"),
    ]
    picked = pick_session(items, TODAY, 5, ["hanging", "missed_gain"], 3, Filter(), False)
    # 1 due; of 4 new, 3 from the weak kinds (most recent first), then the most recent other.
    assert picked == [1, 9, 5, 4, 8]


def test_bullet_on_demand_and_filtered_session() -> None:
    items = [
        c(1, tc="bullet", kind="hanging"),
        c(2, kind="hanging", phase="opening"),
        c(3, kind="hanging"),
        c(4, kind="allows_mate", low=True),
    ]
    assert pick_session(items, TODAY, 5, [], 3, Filter(), True)[0] == 4
    flt = Filter(error_kind="hanging", phase="middlegame")
    assert pick_session(items, TODAY, 5, [], 3, flt, False) == [3]
    assert pick_session(items, TODAY, 5, [], 3, Filter(low_time=True), False) == [4]


def test_streak() -> None:
    days = [TODAY, TODAY - timedelta(days=1), TODAY - timedelta(days=2), TODAY - timedelta(days=4)]
    assert streak(days, TODAY) == 3
    assert streak(days[1:], TODAY) == 2  # today not done yet: counts up to yesterday
    assert streak([], TODAY) == 0


def test_exclusions() -> None:
    # Already winning (or losing) before the opponent's move and still: decided.
    assert exclusion(90, 92, 0) == "decided" and exclusion(10, 8, 0) == "decided"
    # A blunder of the opponent gave the chance: the position "looks" won, it is an exercise.
    assert exclusion(97, 52, 0) is None
    assert exclusion(60, 55, 2) == "unclear"
    assert exclusion(60, 55, 1) is None  # one alternative: both count as right
