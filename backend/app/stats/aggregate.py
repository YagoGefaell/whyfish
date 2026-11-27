"""Statistics from the precalculated rows (phase 6b). Pure: rows in, figures and texts out.

Focused on what to improve: every figure keeps the positions that explain it (examples ->
review at that move). "Errors" are ?, ?? and ✗ (mistake, blunder, miss).
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.config import STATS, StatsThresholds

ERRORS = ("mistake", "blunder", "miss")

KIND_LABEL = {
    "hanging": "Pieza colgada",
    "tactic_allowed": "Táctica del rival no vista",
    "allows_mate": "Mate permitido",
    "missed_mate": "Mate no visto",
    "missed_gain": "Ganancia no vista",
    "loses_material": "Material perdido",
    "positional": "Sin causa táctica clara",
}
# Weak point sentence for each error type (the user's habit).
KIND_HABIT = {
    "hanging": "Dejas piezas sin defensa",
    "tactic_allowed": "No ves las tácticas del rival (dobles ataques, clavadas…)",
    "allows_mate": "Permites mates",
    "missed_mate": "No ves mates a tu favor",
    "missed_gain": "Se te escapan ganancias de material",
    "loses_material": "Pierdes material con jugadas que el rival refuta",
}
KIND_ADVICE = {
    "hanging": "Antes de mover, comprueba qué piezas quedan sin defensa y qué deja de proteger "
    "la pieza que mueves.",
    "tactic_allowed": "Mira las casillas desde las que una pieza rival atacaría dos cosas a la "
    "vez o clavaría una de tus piezas.",
    "allows_mate": "Antes de cada jugada, repasa los jaques y las capturas que tendría el rival.",
    "missed_mate": "Cuando el rey rival está expuesto, busca primero los jaques.",
    "missed_gain": "En cada jugada busca jaques, capturas y amenazas: a veces el rival deja algo "
    "sin defensa.",
    "loses_material": "Antes de mover, piensa cuál sería la respuesta más fuerte del rival.",
}
PHASE_LABEL = {"opening": "Apertura", "middlegame": "Medio juego", "endgame": "Final"}
PHASE_IN = {
    "opening": "en la apertura",
    "middlegame": "en el medio juego",
    "endgame": "en el final",
}
COLOR_IN = {"white": "Con blancas", "black": "Con negras"}


@dataclass(frozen=True)
class GameRow:
    game_id: int
    date: datetime
    color: str  # "white" | "black"
    opponent: str | None
    accuracy: float | None
    result: str | None  # win | draw | loss
    opening_family: str | None
    opening_name: str | None


@dataclass(frozen=True)
class MoveRow:
    game_id: int
    ply: int
    san: str
    classification: str
    delta: float
    phase: str
    error_kind: str | None
    low_time: bool | None


@dataclass(frozen=True)
class Example:
    game_id: int
    ply: int
    san: str
    classification: str
    delta: float
    date: datetime
    opponent: str | None


@dataclass(frozen=True)
class AccuracyPoint:
    game_id: int
    date: datetime
    accuracy: float
    average: float  # moving average up to this game


@dataclass(frozen=True)
class PhaseStat:
    phase: str
    label: str
    moves: int
    errors: int
    per10: float  # errors every 10 moves of the user in that phase
    examples: list[Example]


@dataclass(frozen=True)
class KindStat:
    kind: str
    label: str
    count: int
    mean_delta: float
    examples: list[Example]


@dataclass(frozen=True)
class OpeningStat:
    color: str
    family: str
    games: int
    wins: int
    draws: int
    losses: int
    score: float  # points / games, 0-100
    accuracy: float | None
    worst: bool
    game_ids: list[int]


@dataclass(frozen=True)
class TimeStat:
    games_with_clock: int
    low_moves: int
    low_errors: int
    normal_moves: int
    normal_errors: int
    low_rate: float | None  # errors per move with little time (0-1)
    normal_rate: float | None
    stands_out: bool
    examples: list[Example]


@dataclass(frozen=True)
class WeakPoint:
    key: str
    title: str
    text: str
    advice: str
    cost: float  # win% lost per analysed game
    examples: list[Example]
    # Filter for training these positions (phase 6c): error kind and/or phase.
    train: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Stats:
    games: int  # analysed games matching the filters
    enough: bool
    min_games: int
    accuracy_mean: float | None
    accuracy: list[AccuracyPoint]
    phases: list[PhaseStat]
    kinds: list[KindStat]
    openings: list[OpeningStat]
    time: TimeStat
    weak_points: list[WeakPoint]


def _examples(
    moves: Sequence[MoveRow], games: dict[int, GameRow], t: StatsThresholds
) -> list[Example]:
    """The costliest first."""
    ordered = sorted(moves, key=lambda m: (-m.delta, m.game_id, m.ply))[: t.examples_max]
    return [
        Example(
            m.game_id,
            m.ply,
            m.san,
            m.classification,
            round(m.delta, 1),
            games[m.game_id].date,
            games[m.game_id].opponent,
        )
        for m in ordered
    ]


def _accuracy(games: Sequence[GameRow], t: StatsThresholds) -> list[AccuracyPoint]:
    points: list[AccuracyPoint] = []
    window: list[float] = []
    for g in sorted(games, key=lambda g: (g.date, g.game_id)):
        if g.accuracy is None:
            continue
        window = [*window, g.accuracy][-t.moving_average :]
        points.append(
            AccuracyPoint(
                g.game_id, g.date, round(g.accuracy, 1), round(sum(window) / len(window), 1)
            )
        )
    return points


def _openings(games: Sequence[GameRow], t: StatsThresholds) -> list[OpeningStat]:
    groups: dict[tuple[str, str], list[GameRow]] = defaultdict(list)
    for g in games:
        if g.opening_family and g.result:
            groups[(g.color, g.opening_family)].append(g)
    stats: list[OpeningStat] = []
    for (color, family), rows in groups.items():
        wins = sum(r.result == "win" for r in rows)
        draws = sum(r.result == "draw" for r in rows)
        accs = [r.accuracy for r in rows if r.accuracy is not None]
        stats.append(
            OpeningStat(
                color=color,
                family=family,
                games=len(rows),
                wins=wins,
                draws=draws,
                losses=len(rows) - wins - draws,
                score=round(100 * (wins + 0.5 * draws) / len(rows), 1),
                accuracy=round(sum(accs) / len(accs), 1) if accs else None,
                worst=False,
                game_ids=[r.game_id for r in sorted(rows, key=lambda r: r.date, reverse=True)],
            )
        )
    # The worst: enough games, under 50 % of the points; two per colour at most.
    out: list[OpeningStat] = []
    for color in ("white", "black"):
        mine = sorted(
            (s for s in stats if s.color == color),
            key=lambda s: (-s.games, s.family),
        )
        bad = sorted(
            (s for s in mine if s.games >= t.opening_min_games and s.score < 50),
            key=lambda s: (s.score, s.accuracy or 0),
        )[:2]
        worst = {s.family for s in bad}
        out += [OpeningStat(**{**s.__dict__, "worst": s.family in worst}) for s in mine]
    return out


def _time(moves: Sequence[MoveRow], games: dict[int, GameRow], t: StatsThresholds) -> TimeStat:
    timed = [m for m in moves if m.low_time is not None]
    low = [m for m in timed if m.low_time]
    normal = [m for m in timed if not m.low_time]
    low_errors = [m for m in low if m.classification in ERRORS]
    normal_errors = [m for m in normal if m.classification in ERRORS]
    low_rate = len(low_errors) / len(low) if low else None
    normal_rate = len(normal_errors) / len(normal) if normal else None
    stands_out = (
        low_rate is not None
        and len(low) >= t.time_min_moves
        and low_rate > 0
        and (normal_rate is None or normal_rate == 0 or low_rate >= t.time_weak_ratio * normal_rate)
    )
    return TimeStat(
        games_with_clock=len({m.game_id for m in timed}),
        low_moves=len(low),
        low_errors=len(low_errors),
        normal_moves=len(normal),
        normal_errors=len(normal_errors),
        low_rate=round(low_rate, 3) if low_rate is not None else None,
        normal_rate=round(normal_rate, 3) if normal_rate is not None else None,
        stands_out=stands_out,
        examples=_examples(low_errors, games, t),
    )


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _weak_points(
    games: dict[int, GameRow],
    errors: Sequence[MoveRow],
    openings: Sequence[OpeningStat],
    time: TimeStat,
    low_errors: Sequence[MoveRow],
    t: StatsThresholds,
) -> list[WeakPoint]:
    """Candidates ranked by the win% they cost per analysed game."""
    n = max(1, len(games))
    games_txt = _plural(len(games), "partida", "partidas")
    candidates: list[WeakPoint] = []
    by_kind_phase: dict[tuple[str, str], list[MoveRow]] = defaultdict(list)
    # Only errors with a concrete cause: "positional" means none was found, so it is not a
    # habit the user can work on (it is still listed among the error types, honestly named).
    for m in errors:
        if m.error_kind in KIND_HABIT:
            by_kind_phase[(m.error_kind, m.phase)].append(m)
    for (kind, phase), rows in by_kind_phase.items():
        if len(rows) < t.weak_min_errors:
            continue
        candidates.append(
            WeakPoint(
                key=f"{kind}:{phase}",
                title=f"{KIND_HABIT[kind]} {PHASE_IN[phase]}",
                text=f"{_plural(len(rows), 'vez', 'veces')} en {games_txt}.",
                advice=KIND_ADVICE[kind],
                cost=round(sum(m.delta for m in rows) / n, 1),
                examples=_examples(rows, games, t),
                train={"error_kind": kind, "phase": phase},
            )
        )
    for o in openings:
        if not o.worst:
            continue
        # What the opening costs: the errors of its phase in those games (the later ones are
        # weak points of their own).
        ids = set(o.game_ids)
        rows = [m for m in errors if m.game_id in ids and m.phase == "opening"]
        candidates.append(
            WeakPoint(
                key=f"opening:{o.color}:{o.family}",
                title=f"{COLOR_IN[o.color]}, la {o.family}",
                text=(
                    f"{o.score:.0f} % de los puntos en {_plural(o.games, 'partida', 'partidas')}"
                    f" ({o.wins}-{o.draws}-{o.losses})."
                ),
                advice="Repasa las ideas de esta apertura en tus partidas, o prueba otra.",
                cost=round(sum(m.delta for m in rows) / n, 1),
                examples=_examples(rows, games, t),
            )
        )
    if time.stands_out and time.low_rate is not None:
        ratio = (
            f"{time.low_rate / time.normal_rate:.1f} veces más a menudo"
            if time.normal_rate
            else "mucho más a menudo"
        )
        candidates.append(
            WeakPoint(
                key="time",
                title="Gestión del tiempo",
                text=(
                    f"Con poco reloj cometes errores {ratio}: {time.low_errors} en "
                    f"{_plural(time.low_moves, 'jugada', 'jugadas')} con poco tiempo."
                ),
                advice="Reparte el tiempo: no lo gastes todo al principio y juega más rápido "
                "las jugadas obvias.",
                cost=round(sum(m.delta for m in low_errors) / n, 1),
                examples=_examples(low_errors, games, t),
                train={"low_time": "true"},
            )
        )
    candidates.sort(key=lambda w: (-w.cost, w.key))
    return candidates[: t.weak_points]


def build_stats(
    games: Sequence[GameRow], moves: Sequence[MoveRow], t: StatsThresholds = STATS
) -> Stats:
    """`games`: analysed games matching the filters; `moves`: the user's moves in them."""
    by_id = {g.game_id: g for g in games}
    moves = [m for m in moves if m.game_id in by_id]
    errors = [m for m in moves if m.classification in ERRORS]
    accuracy = _accuracy(games, t)
    phases: list[PhaseStat] = []
    for phase, label in PHASE_LABEL.items():
        in_phase = [m for m in moves if m.phase == phase]
        wrong = [m for m in errors if m.phase == phase]
        phases.append(
            PhaseStat(
                phase=phase,
                label=label,
                moves=len(in_phase),
                errors=len(wrong),
                per10=round(10 * len(wrong) / len(in_phase), 2) if in_phase else 0.0,
                examples=_examples(wrong, by_id, t),
            )
        )
    groups: dict[str, list[MoveRow]] = defaultdict(list)
    for m in errors:
        groups[m.error_kind or "positional"].append(m)
    kinds = sorted(
        (
            KindStat(
                kind=kind,
                label=KIND_LABEL.get(kind, kind),
                count=len(rows),
                mean_delta=round(sum(m.delta for m in rows) / len(rows), 1),
                examples=_examples(rows, by_id, t),
            )
            for kind, rows in groups.items()
        ),
        key=lambda k: (-k.count, -k.mean_delta, k.kind),
    )
    openings = _openings(games, t)
    time = _time(moves, by_id, t)
    low_errors = [m for m in errors if m.low_time]
    values = [p.accuracy for p in accuracy]
    return Stats(
        games=len(games),
        enough=len(games) >= t.min_games,
        min_games=t.min_games,
        accuracy_mean=round(sum(values) / len(values), 1) if values else None,
        accuracy=accuracy,
        phases=phases,
        kinds=kinds,
        openings=openings,
        time=time,
        weak_points=_weak_points(by_id, errors, openings, time, low_errors, t),
    )
