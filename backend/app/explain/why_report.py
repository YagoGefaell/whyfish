"""Review report of "Ver por qué" (Phase 5 acceptance): a self-contained HTML file.

    DATABASE_URL=sqlite:////tmp/x.db uv run python -m app.explain.why_report --out report.html

Reads the user's analysed games of the database (Event starting with "whyfish"), builds the
sequence of every move that has one (extending short lines with the engine, cached in that
database) and picks a FIXED sample (not hand-picked) by bucket. For each: diagrams before the
move and at the end of the sequence, every step with its caption, and the summary.
"""

import argparse
import asyncio
import html
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.svg
from sqlalchemy import Engine as DbEngine
from sqlmodel import Session

from app.analysis.book import default_book
from app.analysis.facts import MoveFacts
from app.analysis.review import build_review
from app.analysis.runner import extend_line
from app.analysis.types import Classification
from app.config import FACTS, Settings, get_settings
from app.db import make_db_engine
from app.engine.pool import PoolManager
from app.engine.stockfish import StockfishEngine
from app.explain.idea import choose_idea
from app.explain.report import COLORS, LABELS, is_user_game, load_games
from app.explain.service import facts_for_ply
from app.explain.why import Why, build_why, needs_extension, why_kind, why_line
from app.models.game import Game

C = Classification
ERRORS = (C.BLUNDER, C.MISTAKE, C.MISS, C.INACCURACY)


@dataclass(frozen=True)
class Item:
    game: Game
    label: str
    you: bool
    facts: MoveFacts
    why: Why
    cached_plies: int  # length of the stored line
    used_plies: int  # length after extending it

    @property
    def mate(self) -> bool:
        return bool(self.why.steps) and self.why.steps[-1].san.endswith("#")


async def collect(db: DbEngine, settings: Settings) -> list[Item]:
    book = default_book()
    with Session(db) as session:
        games = [g for g in load_games(session) if is_user_game(g[0])]
    pools = PoolManager(StockfishEngine.start_for_analysis, settings)
    items: list[Item] = []
    try:
        async with pools.use() as pool, pool.acquire() as engine:
            name = engine.name
        for game, ucis, evals in games:
            user = game.player_color.chess_color
            review = build_review(game.initial_fen, ucis, evals, user, book)
            label = f"{game.white_name or '?'} - {game.black_name or '?'}"
            if game.played_date:
                label += f" ({game.played_date})"
            for m in review.moves:
                kind = why_kind(m.classification)
                if kind is None:
                    continue
                facts = facts_for_ply(game.initial_fen, ucis, evals, review, m.ply, book)
                if m.classification == C.BEST and choose_idea(facts) is None:
                    continue
                line = why_line(facts, kind)
                if line is None:
                    continue
                extended = await extend_line(
                    chess.Board(facts.fen_before),
                    line.ucis,
                    needs_more=needs_extension,
                    pools=pools,
                    db=db,
                    settings=settings,
                    engine_name=name,
                    max_plies=FACTS.consequence_max_plies,
                )
                why = build_why(facts, kind, extended, user)
                items.append(
                    Item(game, label, m.color == user, facts, why, len(line.ucis), len(extended))
                )
    finally:
        await pools.close()
    return items


Bucket = tuple[str, Callable[[Item], bool], int]

BUCKETS: list[Bucket] = [
    (
        "Errores con consecuencia de material",
        lambda i: (
            i.facts.classification in ERRORS and i.why.consequence_ply is not None and not i.mate
        ),
        6,
    ),
    ("Mate", lambda i: i.mate, 1),
    (
        "Sin consecuencia clara",
        lambda i: i.why.kind == "refutation" and i.why.consequence_ply is None,
        1,
    ),
    (
        "Gran jugada (!): por qué fallaba la alternativa",
        lambda i: i.facts.classification == C.GREAT,
        1,
    ),
    (
        "Idea de una jugada buena (★ o !!)",
        lambda i: i.facts.classification in (C.BEST, C.BRILLIANT),
        1,
    ),
]


def pick(items: Sequence[Item]) -> tuple[list[tuple[str, list[Item]]], list[str]]:
    """Per bucket: the user's moves first, then the opponent's; bigger Δ first, then game
    order. A move is used once."""
    used: set[tuple[int | None, int]] = set()
    chosen: list[tuple[str, list[Item]]] = []
    notes: list[str] = []
    for title, accepts, n in BUCKETS:
        pool = [i for i in items if accepts(i) and (i.game.id, i.facts.ply) not in used]
        pool.sort(key=lambda i: (not i.you, -i.facts.delta, i.game.id or 0, i.facts.ply))
        taken = pool[:n]
        used.update((i.game.id, i.facts.ply) for i in taken)
        if len(taken) < n:
            notes.append(f"«{title}»: solo {len(taken)} de {n} en tus partidas.")
        chosen.append((title, taken))
    return chosen, notes


def _svg(fen: str, orientation: chess.Color, last: str | None, mark: str | None, bad: bool) -> str:
    board = chess.Board(fen)
    fill = {}
    if mark:
        fill[chess.parse_square(mark)] = "#dc262699" if bad else "#16a34a99"
    lastmove = chess.Move.from_uci(last) if last else None
    return chess.svg.board(board, orientation=orientation, lastmove=lastmove, fill=fill, size=260)


def _marked(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"\[\[([^\[\]]+)\]\]", r'<span class="mv">\1</span>', escaped)


def _article(n: int, item: Item) -> str:
    w, f = item.why, item.facts
    orientation = item.game.player_color.chess_color
    last = w.steps[-1] if w.steps else None
    rows = []
    for st in w.steps:
        flags = []
        if st.defense:
            flags.append('<span class="flag def">mejor defensa</span>')
        if st.consequence:
            flags.append(f'<span class="flag {w.tone}">consecuencia</span>')
        if st.arrows:
            arrows = ", ".join(f"{a.from_square}→{a.to_square}" for a in st.arrows)
            flags.append(f'<span class="flag arr">amenaza {arrows}</span>')
        cls = ' class="cons"' if st.consequence else (' class="defrow"' if st.defense else "")
        rows.append(
            f"<tr{cls}><td class='lbl'>{html.escape(st.label)}</td>"
            f"<td>{html.escape(st.caption)}</td><td>{''.join(flags)}</td></tr>"
        )
    who = "tu jugada" if item.you else "jugada del rival"
    ext = (
        f"línea guardada de {item.cached_plies} medias jugadas, extendida con el motor a "
        f"{item.used_plies}"
        if item.used_plies > item.cached_plies
        else f"línea guardada de {item.cached_plies} medias jugadas (sin extender)"
    )
    final = (
        _svg(
            last.fen,
            orientation,
            last.uci,
            last.uci[2:4] if last.consequence else None,
            w.tone == "bad",
        )
        if last
        else ""
    )
    return (
        f'<article id="w{n}"><h3>{n}. {html.escape(w.title)} '
        f'<span class="cls" style="background:{COLORS[f.classification]}">'
        f"{LABELS[f.classification]}</span></h3>"
        f'<p class="src">{html.escape(item.label)} · {who} · '
        f"{'Ver por qué' if w.kind == 'refutation' else 'Ver la idea'} · {ext}</p>"
        f'<div class="boards"><figure>{_svg(w.start_fen, orientation, None, None, False)}'
        f"<figcaption>Antes de la jugada</figcaption></figure>"
        f"<figure>{final}<figcaption>Final de la secuencia</figcaption></figure></div>"
        f'<table class="steps"><tbody>{"".join(rows)}</tbody></table>'
        f'<div class="summary {w.tone}"><strong>Resumen:</strong> {_marked(w.summary)}</div>'
        "</article>"
    )


def render(chosen: list[tuple[str, list[Item]]], notes: list[str], total: int) -> str:
    body: list[str] = []
    n = 0
    for title, taken in chosen:
        body.append(f"<h2>{html.escape(title)} <small>({len(taken)})</small></h2>")
        for item in taken:
            n += 1
            body.append(_article(n, item))
    notes_html = "".join(f"<li>{html.escape(x)}</li>" for x in notes) or "<li>Ninguna.</li>"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ver por qué · Fase 5</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px;
  background: #fafaf9; color: #1c1917; line-height: 1.5; }}
h2 {{ margin-top: 40px; border-bottom: 2px solid #d6d3d1; }}
article {{ padding: 16px; margin: 16px 0; background: #fff; border: 1px solid #e7e5e4;
  border-radius: 10px; }}
.boards {{ display: flex; gap: 16px; flex-wrap: wrap; }}
figure {{ margin: 0; }} figcaption {{ font-size: 13px; color: #57534e; text-align: center; }}
.cls {{ color: #fff; border-radius: 6px; padding: 1px 8px; font-size: 14px; }}
.src {{ color: #57534e; font-size: 14px; margin-top: 0; }}
table.steps {{ border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 15px; }}
.steps td {{ border-top: 1px solid #e7e5e4; padding: 4px 8px; vertical-align: top; }}
.steps td.lbl {{ font-family: ui-monospace, monospace; white-space: nowrap; width: 7em; }}
.steps tr.defrow td {{ font-style: italic; color: #44403c; }}
.steps tr.cons td {{ font-weight: 600; }}
.flag {{ font-size: 12px; border-radius: 4px; padding: 0 6px; margin-right: 4px;
  white-space: nowrap; }}
.flag.def {{ border: 1px dashed #78716c; }} .flag.arr {{ background: #fee2e2; }}
.flag.bad {{ background: #dc2626; color: #fff; }} .flag.good {{ background: #16a34a; color: #fff; }}
.summary {{ margin-top: 12px; padding: 8px 12px; border-radius: 8px; font-size: 17px; }}
.summary.bad {{ background: #fef2f2; border: 1px solid #fecaca; }}
.summary.good {{ background: #f0fdf4; border: 1px solid #bbf7d0; }}
.mv {{ background: #e7e5e4; border-radius: 4px; padding: 0 4px; font-weight: 600;
  font-family: ui-monospace, monospace; }}
</style></head><body>
<h1>Ver por qué · Fase 5</h1>
<p>{n} secuencias de tus partidas, elegidas de {total} con una regla fija: por grupo, primero tus
jugadas y luego las del rival; dentro de cada grupo, la de mayor caída de evaluación primero.
Cada secuencia llega hasta su punto de consecuencia (o 8 medias jugadas si no hay una clara);
las líneas cortas se extienden con el motor. En cursiva, la mejor defensa del motor (no lo que
se jugó).</p>
<h3>Notas sobre la muestra</h3><ul>{notes_html}</ul>
{"".join(body)}
</body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Informe de «Ver por qué» (Fase 5).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    settings = get_settings()
    db = make_db_engine(settings.database_url)
    items = asyncio.run(collect(db, settings))
    if not items:
        print("No hay partidas tuyas analizadas en la base.", file=sys.stderr)
        sys.exit(1)
    chosen, notes = pick(items)
    Path(args.out).write_text(render(chosen, notes, len(items)), encoding="utf-8")
    print(f"{sum(len(t) for _, t in chosen)} secuencias → {args.out}")
    for note in notes:
        print("  ·", note)


if __name__ == "__main__":
    main()
