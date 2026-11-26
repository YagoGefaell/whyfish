"""Review report of template explanations (Phase 4 acceptance): a self-contained HTML file.

    DATABASE_URL=sqlite:////tmp/x.db uv run python -m app.explain.report --out report.html

Reads every analysed game of the database, explains every move and picks a FIXED sample (not
hand-picked) by category. Games whose Event starts with "whyfish" are the user's.
For each move: diagram with the annotations, classification, level 1 and level 2 texts, and the
facts, marking those the text used (so a vague sentence can be traced to missing facts or to
the template).
"""

import argparse
import html
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.svg
from sqlmodel import Session, col, select

from app.analysis.book import default_book
from app.analysis.detectors.lines import LineOutcome
from app.analysis.facts import MoveEffects, MoveFacts
from app.analysis.positions import game_positions
from app.analysis.review import build_review
from app.analysis.runner import lines_from_json
from app.analysis.sacrifice import Sacrifice
from app.analysis.types import Classification, PositionEval
from app.config import get_settings
from app.db import make_db_engine
from app.explain.idea import Annotation
from app.explain.service import Explanation, explain, facts_for_ply
from app.models.analysis import AnalysisJob, AnalysisStatus, PositionAnalysis
from app.models.game import Game, Move

C = Classification
LABELS = {
    C.BOOK: "Teoría",
    C.BRILLIANT: "Brillante !!",
    C.GREAT: "Gran jugada !",
    C.BEST: "Mejor ★",
    C.EXCELLENT: "Excelente",
    C.GOOD: "Buena",
    C.INACCURACY: "Imprecisión ?!",
    C.MISTAKE: "Error ?",
    C.BLUNDER: "Grave error ??",
    C.MISS: "Oportunidad perdida ✗",
}
COLORS = {
    C.BOOK: "#a88865",
    C.BRILLIANT: "#1baca6",
    C.GREAT: "#5c8bb0",
    C.BEST: "#81b64c",
    C.EXCELLENT: "#81b64c",
    C.GOOD: "#77915f",
    C.INACCURACY: "#f7c631",
    C.MISTAKE: "#ffa459",
    C.BLUNDER: "#fa412d",
    C.MISS: "#ff7769",
}
# Sample: (title, categories, how many). Fixed rule, see `pick`.
BUCKETS: list[tuple[str, tuple[Classification, ...], int]] = [
    ("Errores (?? y ?)", (C.BLUNDER, C.MISTAKE), 5),
    ("Imprecisiones (?!)", (C.INACCURACY,), 4),
    ("Oportunidades perdidas (✗)", (C.MISS,), 2),
    ("Grandes jugadas y brillantes (! y !!)", (C.GREAT, C.BRILLIANT), 4),
    ("Mejores jugadas explicadas (★)", (C.BEST,), 2),
    ("Excelentes y buenas", (C.EXCELLENT, C.GOOD), 3),
]
ARROW = {"threat": "#dc2626", "attack": "#f59e0b"}
FILL = {"danger": "#dc262680", "target": "#f59e0b80"}


@dataclass(frozen=True)
class Item:
    game: Game
    game_label: str
    user_game: bool
    you: bool
    facts: MoveFacts
    level1: Explanation
    level2: Explanation


def load_games(session: Session) -> list[tuple[Game, list[str], list[PositionEval]]]:
    games = session.exec(select(Game).order_by(col(Game.id))).all()
    out = []
    for game in games:
        job = session.exec(select(AnalysisJob).where(AnalysisJob.game_id == game.id)).first()
        if job is None or job.status is not AnalysisStatus.DONE:
            continue
        moves = session.exec(
            select(Move).where(Move.game_id == game.id).order_by(col(Move.ply))
        ).all()
        ucis = [m.uci for m in moves]
        positions = game_positions(game.initial_fen, ucis)
        rows = session.exec(
            select(PositionAnalysis).where(
                PositionAnalysis.settings_key == job.settings_key,
                col(PositionAnalysis.key).in_([p.key for p in positions]),
            )
        ).all()
        cache = {r.key: lines_from_json(r.lines_json) for r in rows}
        evals = [p.terminal or PositionEval(lines=cache[p.key]) for p in positions]
        out.append((game, ucis, evals))
    return out


def is_user_game(game: Game) -> bool:
    return (game.event or "").startswith("whyfish")


def collect(session: Session) -> list[Item]:
    book = default_book()
    items: list[Item] = []
    for game, ucis, evals in load_games(session):
        perspective = game.player_color.chess_color
        review = build_review(game.initial_fen, ucis, evals, perspective, book)
        label = f"{game.white_name or '?'} - {game.black_name or '?'}"
        if game.played_date:
            label += f" ({game.played_date})"
        for m in review.moves:
            facts = facts_for_ply(game.initial_fen, ucis, evals, review, m.ply, book)
            you = m.color == perspective
            items.append(
                Item(
                    game,
                    label,
                    is_user_game(game),
                    you,
                    facts,
                    explain(facts, 1, you),
                    explain(facts, 2, you),
                )
            )
    return items


def _round_robin(items: Sequence[Item]) -> list[Item]:
    """One move per game in turn (game order, then ply order), to spread the sample."""
    by_game: dict[int | None, list[Item]] = {}
    for item in items:
        by_game.setdefault(item.game.id, []).append(item)
    queues = list(by_game.values())
    out: list[Item] = []
    while any(queues):
        for queue in queues:
            if queue:
                out.append(queue.pop(0))
    return out


def candidates(items: Sequence[Item], categories: Iterable[Classification]) -> list[Item]:
    """Explained moves of these categories: the user's own moves in their games first, then
    the bot's moves in those games, then the fixtures; round robin by game inside each group."""
    wanted = set(categories)
    pool = [i for i in items if i.facts.classification in wanted and i.level1.text]
    groups = [
        [i for i in pool if i.user_game and i.you],
        [i for i in pool if i.user_game and not i.you],
        [i for i in pool if not i.user_game],
    ]
    return [i for group in groups for i in _round_robin(group)]


def pick(items: Sequence[Item]) -> tuple[list[tuple[str, list[Item]]], list[str]]:
    """Fixed sample of 20. Missing ✗ go to the error bucket. Returns notes on fill-ins."""
    notes: list[str] = []
    chosen: list[tuple[str, list[Item]]] = []
    spare = 0
    for title, cats, n in BUCKETS:
        pool = candidates(items, cats)
        if cats == (C.MISS,) and len(pool) < n:
            spare += n - len(pool)
            notes.append(
                f"Solo hay {len(pool)} oportunidad(es) perdida(s) explicada(s); los "
                f"{n - len(pool)} hueco(s) pasan a «Errores»."
            )
        taken = pool[:n]
        user = sum(1 for i in taken if i.user_game)
        if user < len(taken):
            notes.append(
                f"{title}: {user} de {len(taken)} de tus partidas; el resto, de los fixtures."
            )
        if len(taken) < n and cats != (C.MISS,):
            notes.append(f"{title}: solo {len(taken)} de {n} disponibles.")
        chosen.append((title, taken))
    if spare:
        title, taken = chosen[0]
        pool = candidates(items, BUCKETS[0][1])
        extra = [i for i in pool if i not in taken][:spare]
        chosen[0] = (title, taken + extra)
    return chosen, notes


# --- HTML ------------------------------------------------------------------------------------


def _svg(item: Item, annotations: Sequence[Annotation]) -> str:
    facts = item.facts
    board = chess.Board(facts.fen_after)
    move = chess.Move.from_uci(facts.uci)
    arrows = [
        chess.svg.Arrow(
            chess.parse_square(a.from_square),
            chess.parse_square(a.to_square),
            color=ARROW[a.role],
        )
        for a in annotations
        if a.kind == "arrow" and a.from_square and a.to_square
    ]
    fill = {
        chess.parse_square(a.square): FILL[a.role]
        for a in annotations
        if a.kind == "square" and a.square
    }
    orientation = item.game.player_color.chess_color if item.user_game else chess.WHITE
    return chess.svg.board(
        board, orientation=orientation, lastmove=move, arrows=arrows, fill=fill, size=300
    )


def _marked(text: str | None) -> str:
    if text is None:
        return "<em>(sin explicación: jugada obvia)</em>"
    escaped = html.escape(text)
    escaped = re.sub(r"\[\[([^\[\]]+)\]\]", r'<span class="mv">\1</span>', escaped)
    return "".join(f"<p>{p}</p>" for p in escaped.split("\n\n"))


def _line(line: LineOutcome | None) -> str:
    if line is None:
        return "—"
    parts = [" ".join(line.sans) or "(vacía)", f"material {line.material:+d}"]
    if line.mate is not None:
        parts.append(f"mate {line.mate:+d}")
    parts.append(f"win {line.win:.0f}%")
    if line.motifs:
        motifs = ", ".join(
            f"{m.kind}@{m.index} por {m.by.square} → {'/'.join(t.square for t in m.targets)}"
            for m in line.motifs
        )
        parts.append(f"motivos: {motifs}")
    if line.captures:
        caps = ", ".join(
            f"{c.index}:{c.by.piece}{c.by.square}x{c.captured.piece}{c.captured.square}"
            for c in line.captures
        )
        parts.append(f"capturas: {caps}")
    return " · ".join(parts)


def _effects_rows(prefix: str, e: MoveEffects | None) -> list[tuple[str, str]]:
    if e is None:
        return []
    rows = [
        (
            f"{prefix}.hanging",
            ", ".join(f"{h.piece.piece} {h.piece.square} (-{h.loss})" for h in e.hanging),
        ),
        (
            f"{prefix}.threats",
            ", ".join(
                "mate" if t.kind == "mate" else f"{t.target.piece} {t.target.square} (+{t.gain})"
                for t in e.threats
            ),
        ),
        (
            f"{prefix}.parried",
            ", ".join(
                f"{p.how}: {p.threat.target.piece} {p.threat.target.square}" for p in e.parried
            ),
        ),
        (f"{prefix}.pawns", ", ".join(f"{p.kind} {p.where}" for p in e.pawns)),
        (
            f"{prefix}.motifs",
            ", ".join(f"{m.kind} → {'/'.join(t.square for t in m.targets)}" for m in e.motifs),
        ),
        (f"{prefix}.weakens_king", "sí" if e.weakens_king else ""),
        (f"{prefix}.develops", "sí" if e.develops else ""),
        (f"{prefix}.castles", "sí" if e.castles else ""),
    ]
    return rows


def _facts_table(item: Item) -> str:
    f = item.facts
    used = set(item.level1.used)
    rows: list[tuple[str, str]] = [
        (
            "classification",
            f"{f.classification} · Δ {f.delta:.1f} · win {f.win_before:.0f}→{f.win_after:.0f}",
        ),
        ("opening", f.opening or ""),
        ("material_before", f"{f.material_before:+d}"),
        ("played_line", _line(f.played_line)),
        ("best_line", "(es la jugada hecha)" if f.is_best else _line(f.best_line)),
        ("second_line", _line(f.second_line) if f.second_line else ""),
        ("sacrifice", _sacrifice(f.sacrifice)),
        ("sacrifice_line", _line(f.sacrifice_line) if f.sacrifice_line else ""),
        *_effects_rows("played", f.played),
        *_effects_rows("best", f.best),
    ]

    def is_used(key: str) -> bool:
        return any(u == key or u.startswith(key + ".") for u in used)

    out = []
    for key, value in rows:
        if not value and not is_used(key):
            continue
        mark = "✓" if is_used(key) else ""
        cls = ' class="used"' if mark else ""
        out.append(
            f"<tr{cls}><td>{mark}</td><td><code>{key}</code></td><td>{html.escape(value)}</td></tr>"
        )
    return '<table class="facts">' + "".join(out) + "</table>"


def _sacrifice(s: Sacrifice | None) -> str:
    if s is None:
        return ""
    how = "cota del MultiPV" if s.bound else f"línea {' '.join(s.line[:4])}…"
    end = "" if s.line_end is None else f"; material al final {s.line_end:+d}"
    return f"pieza de {s.square}, el rival gana {s.amount} (SEE); {how} ({s.win:.0f} %){end}"


def _diagnosis(item: Item) -> str:
    e = item.level1
    if e.idea == "positional" and not e.used:
        return '<p class="warn">Frase genérica: ningún hecho la respalda (faltan hechos).</p>'
    if e.idea == "slightly_worse" and not e.used:
        return '<p class="warn">Sin motivo concreto para la mejor (faltan hechos).</p>'
    return ""


def _move_label(item: Item) -> str:
    ply = item.facts.ply
    return f"{ply // 2 + 1}{'.' if ply % 2 == 0 else '…'} {item.facts.san}"


def render(chosen: list[tuple[str, list[Item]]], notes: list[str], total: int) -> str:
    count = sum(len(t) for _, t in chosen)
    user = sum(1 for _, t in chosen for i in t if i.user_game)
    body: list[str] = []
    n = 0
    for title, taken in chosen:
        body.append(f"<h2>{html.escape(title)} <small>({len(taken)})</small></h2>")
        for item in taken:
            n += 1
            f = item.facts
            color = COLORS[f.classification]
            who = "tu jugada" if item.you else "jugada del rival"
            source = "tu partida" if item.user_game else "fixture"
            body.append(
                f'<article id="e{n}"><div class="board">{_svg(item, item.level1.annotations)}'
                f'<p class="fen">{html.escape(f.fen_before)}</p></div><div class="text">'
                f"<h3>{n}. {html.escape(_move_label(item))} "
                f'<span class="cls" style="background:{color}">'
                f"{LABELS[f.classification]}</span></h3>"
                f'<p class="src">{html.escape(item.game_label)} · {source} · {who} · '
                f"idea: <code>{item.level1.idea}</code></p>"
                f'<div class="l1"><h4>Nivel 1</h4>{_marked(item.level1.text)}</div>'
                f"{_diagnosis(item)}"
                f"<details><summary>Nivel 2</summary>{_marked(item.level2.text)}</details>"
                f"<details><summary>Hechos (✓ = usados en el nivel 1)</summary>"
                f"{_facts_table(item)}</details></div></article>"
            )
    notes_html = "".join(f"<li>{html.escape(x)}</li>" for x in notes) or "<li>Ninguna.</li>"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Explicaciones Fase 4</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px;
  background: #fafaf9; color: #1c1917; line-height: 1.5; }}
h1 {{ margin-bottom: 4px; }}
h2 {{ margin-top: 40px; border-bottom: 2px solid #d6d3d1; }}
article {{ display: flex; gap: 20px; padding: 16px; margin: 16px 0; background: #fff;
  border: 1px solid #e7e5e4; border-radius: 10px; flex-wrap: wrap; }}
.board {{ flex: 0 0 300px; }} .text {{ flex: 1 1 380px; min-width: 0; }}
.fen {{ font: 11px monospace; color: #78716c; word-break: break-all; }}
.cls {{ color: #fff; border-radius: 6px; padding: 1px 8px; font-size: 14px; }}
.src {{ color: #57534e; font-size: 14px; margin-top: 0; }}
.l1 {{ background: #f5f5f4; border-radius: 8px; padding: 2px 12px; font-size: 17px; }}
.mv {{ background: #e7e5e4; border-radius: 4px; padding: 0 4px; font-weight: 600;
  font-family: ui-monospace, monospace; }}
.warn {{ color: #b45309; font-weight: 600; }}
details {{ margin-top: 8px; }} summary {{ cursor: pointer; font-weight: 600; }}
table.facts {{ border-collapse: collapse; font-size: 13px; width: 100%; }}
.facts td {{ border-top: 1px solid #e7e5e4; padding: 3px 6px; vertical-align: top; }}
.facts tr.used {{ background: #ecfccb; }}
.legend span {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px;
  vertical-align: middle; margin: 0 4px 0 12px; }}
</style></head><body>
<h1>Explicaciones por plantilla · Fase 4</h1>
<p>{count} jugadas ({user} de tus partidas), elegidas de {total} jugadas analizadas con una regla
fija: por categoría, primero tus jugadas en tus partidas, luego las del bot en ellas y después los
fixtures; dentro de cada grupo, una jugada por partida por turnos, en orden de partida y jugada.</p>
<p class="legend">Tablero: posición tras la jugada.
<span style="background:#dc2626"></span>amenaza del rival
<span style="background:#dc262680"></span>pieza en peligro
<span style="background:#f59e0b"></span>ataque propio
<span style="background:#f59e0b80"></span>pieza objetivo</p>
<h3>Notas sobre la muestra</h3><ul>{notes_html}</ul>
{"".join(body)}
</body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Informe de explicaciones (Fase 4).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    settings = get_settings()
    engine = make_db_engine(settings.database_url)
    with Session(engine) as session:
        items = collect(session)
    if not items:
        print("No hay partidas analizadas en la base.", file=sys.stderr)
        sys.exit(1)
    chosen, notes = pick(items)
    Path(args.out).write_text(render(chosen, notes, len(items)), encoding="utf-8")
    print(f"{sum(len(t) for _, t in chosen)} explicaciones → {args.out}")
    for note in notes:
        print("  ·", note)


if __name__ == "__main__":
    main()
