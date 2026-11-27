"""Statistics from precalculated rows (pure)."""

from datetime import UTC, datetime, timedelta

from app.config import StatsThresholds
from app.play.rules import PlayerColor
from app.stats.aggregate import GameRow, MoveRow, build_stats
from app.stats.insights import clock_initial, is_low_time, user_result

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def game(
    i: int,
    *,
    color: str = "white",
    result: str = "loss",
    family: str = "Sicilian Defense",
    accuracy: float = 70.0,
) -> GameRow:
    return GameRow(i, T0 + timedelta(days=i), color, f"rival{i}", accuracy, result, family, family)


def move(
    g: int,
    ply: int,
    cls: str = "best",
    *,
    delta: float = 0.0,
    phase: str = "middlegame",
    kind: str | None = None,
    low: bool | None = None,
) -> MoveRow:
    return MoveRow(g, ply, f"m{ply}", cls, delta, phase, kind, low)


def test_clock_helpers() -> None:
    assert clock_initial("600") == 600 and clock_initial("180+2") == 180
    assert clock_initial("1/259200") is None and clock_initial("-") is None
    assert is_low_time(25, 600) is True and is_low_time(35, 600) is False  # 30 s
    assert is_low_time(17, 180) is True and is_low_time(19, 180) is False  # 10 % = 18 s
    assert is_low_time(None, 600) is None and is_low_time(10, None) is None
    assert user_result("0-1", PlayerColor.BLACK) == "win"
    assert user_result("1/2-1/2", PlayerColor.WHITE) == "draw"
    assert user_result("*", PlayerColor.WHITE) is None


def test_phases_kinds_and_examples() -> None:
    games = [game(i) for i in range(4)]
    moves = [
        move(0, 10, "blunder", delta=40, kind="hanging"),
        move(1, 12, "mistake", delta=15, kind="hanging"),
        move(2, 14, "blunder", delta=30, kind="hanging"),
        move(3, 4, "miss", delta=20, phase="opening", kind="missed_gain"),
        move(3, 6, "inaccuracy", delta=6, phase="opening", kind="positional"),  # not an error
        *[move(i, 20 + i, "best", phase="middlegame") for i in range(4)],
    ]
    stats = build_stats(games, moves)
    middle = next(p for p in stats.phases if p.phase == "middlegame")
    assert (middle.moves, middle.errors, middle.per10) == (7, 3, 4.29)
    assert [e.delta for e in middle.examples] == [40, 30, 15]  # costliest first
    assert [(k.kind, k.count) for k in stats.kinds] == [("hanging", 3), ("missed_gain", 1)]
    assert stats.kinds[0].label == "Pieza colgada"
    assert not stats.enough and stats.min_games == 10


def test_weak_points_ranked_by_cost_with_training_filter() -> None:
    games = [game(i, result="loss") for i in range(5)]
    moves = [move(i, 10, "blunder", delta=30, kind="hanging") for i in range(4)]
    moves += [
        move(i, 30, "mistake", delta=12, phase="endgame", kind="loses_material") for i in range(3)
    ]
    stats = build_stats(games, moves)
    titles = [w.title for w in stats.weak_points]
    assert titles[0] == "Dejas piezas sin defensa en el medio juego"
    assert stats.weak_points[0].text == "4 veces en 5 partidas."
    assert stats.weak_points[0].train == {"error_kind": "hanging", "phase": "middlegame"}
    assert "Pierdes material con jugadas que el rival refuta en el final" in titles
    # The opening (5 losses with the Sicilian) is a weak point too.
    assert any(w.key == "opening:white:Sicilian Defense" for w in stats.weak_points)


def test_openings_worst_needs_enough_games() -> None:
    games = [
        game(0, result="loss", family="French Defense"),
        game(1, result="loss", family="French Defense"),
        *[game(i, result="loss", family="Italian Game") for i in range(2, 5)],
        *[game(i, result="win", family="Ruy Lopez") for i in range(5, 8)],
    ]
    by = {o.family: o for o in build_stats(games, []).openings}
    assert by["Italian Game"].worst and by["Italian Game"].score == 0
    assert not by["French Defense"].worst  # only 2 games
    assert not by["Ruy Lopez"].worst and by["Ruy Lopez"].score == 100


def test_time_management_stands_out() -> None:
    t = StatsThresholds(time_min_moves=4)
    games = [game(i) for i in range(2)]
    low = [
        move(0, p, "blunder" if p < 3 else "best", delta=20 if p < 3 else 0, low=True)
        for p in range(5)
    ]
    normal = [
        move(1, p, "mistake" if p == 0 else "best", delta=10 if p == 0 else 0, low=False)
        for p in range(10)
    ]
    stats = build_stats(games, low + normal, t)
    assert (stats.time.low_moves, stats.time.low_errors, stats.time.low_rate) == (5, 3, 0.6)
    assert stats.time.normal_rate == 0.1 and stats.time.stands_out
    point = next(w for w in stats.weak_points if w.key == "time")
    assert point.title == "Gestión del tiempo" and "6.0 veces más a menudo" in point.text
    # Not enough low-time moves: it does not stand out.
    assert not build_stats(games, low + normal).time.stands_out


def test_accuracy_series_and_moving_average() -> None:
    games = [game(i, accuracy=a) for i, a in enumerate([60, 70, 80, 90, 100, 50])]
    stats = build_stats(games, [], StatsThresholds(moving_average=3))
    assert [p.average for p in stats.accuracy] == [60, 65, 70, 80, 90, 80]
    assert stats.accuracy_mean == 75


def test_errors_without_a_concrete_cause_are_not_a_weak_point() -> None:
    games = [game(i) for i in range(5)]
    moves = [move(i, 10, "mistake", delta=30, kind="positional") for i in range(5)]
    stats = build_stats(games, moves)
    assert [k.label for k in stats.kinds] == ["Sin causa táctica clara"]
    assert not any(w.key.startswith("positional") for w in stats.weak_points)
