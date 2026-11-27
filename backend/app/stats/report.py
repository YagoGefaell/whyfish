# ruff: noqa: E501, RUF001  (HTML template: long lines and typographic characters)
"""Statistics report (phase 6b acceptance): a self-contained HTML file.

    DATABASE_URL=sqlite:////tmp/x.db uv run python -m app.stats.report --out report.html

Computes the precalculated rows of analysed games that lack them, then renders the
statistics with the default filter (real games: Lichess, Chess.com, PGN), as the page shows
them, with board diagrams for the weak points' examples.
"""

import argparse
import html
import sys
from pathlib import Path

import chess
import chess.svg
from sqlmodel import Session, col, select

from app.analysis.runner import AnalysisService
from app.config import get_settings
from app.db import init_db, make_db_engine
from app.engine.pool import PoolManager
from app.engine.stockfish import StockfishEngine
from app.models.game import Game, Move
from app.stats.aggregate import Example, Stats
from app.stats.insights import InsightService
from app.stats.queries import StatsFilters, StatsResult, load_stats

SYMBOL = {"blunder": "??", "mistake": "?", "miss": "✗", "inaccuracy": "?!"}


def _label(e: Example) -> str:
    number = e.ply // 2 + 1
    return f"{number}{'.' if e.ply % 2 == 0 else '…'}{e.san}{SYMBOL.get(e.classification, '')}"


def _example(e: Example) -> str:
    who = html.escape(e.opponent or "?")
    return (
        f"<li><code>{html.escape(_label(e))}</code> vs {who} · {e.date:%d/%m/%Y} · "
        f"−{e.delta:.0f} % <span class='ref'>(/review/{e.game_id}?ply={e.ply})</span></li>"
    )


def _examples(examples: list[Example], n: int = 5) -> str:
    if not examples:
        return "<p class='muted'>Sin posiciones.</p>"
    return "<ul>" + "".join(_example(e) for e in examples[:n]) + "</ul>"


def _diagram(session: Session, e: Example) -> str:
    game = session.get(Game, e.game_id)
    if game is None:
        return ""
    moves = session.exec(
        select(Move).where(Move.game_id == e.game_id).order_by(col(Move.ply))
    ).all()
    board = chess.Board(game.initial_fen)
    for m in moves[: e.ply]:
        board.push_uci(m.uci)
    played = chess.Move.from_uci(moves[e.ply].uci)
    svg = chess.svg.board(
        board,
        orientation=game.player_color.chess_color,
        arrows=[chess.svg.Arrow(played.from_square, played.to_square, color="#dc2626cc")],
        size=200,
    )
    return f"<figure>{svg}<figcaption>{html.escape(_label(e))} (flecha: lo jugado)</figcaption></figure>"


def _accuracy_svg(stats: Stats) -> str:
    points = stats.accuracy
    if not points:
        return ""
    w, h, pad = 640, 170, 26
    x = [pad + i * (w - 2 * pad) / max(1, len(points) - 1) for i in range(len(points))]

    def y(v: float) -> float:
        return h - pad - v * (h - 2 * pad) / 100

    line = " ".join(
        f"{'M' if i == 0 else 'L'}{x[i]:.1f},{y(p.average):.1f}" for i, p in enumerate(points)
    )
    dots = "".join(
        f"<circle cx='{x[i]:.1f}' cy='{y(p.accuracy):.1f}' r='4' fill='#78716c'>"
        f"<title>{p.date:%d/%m/%Y}: {p.accuracy:.1f} %</title></circle>"
        for i, p in enumerate(points)
    )
    grid = "".join(
        f"<line x1='{pad}' x2='{w - pad}' y1='{y(v)}' y2='{y(v)}' stroke='#e7e5e4'/>"
        f"<text x='2' y='{y(v) + 4}' font-size='10' fill='#a8a29e'>{v}</text>"
        for v in (25, 50, 75)
    )
    return (
        f"<svg viewBox='0 0 {w} {h}' width='100%'>{grid}"
        f"<path d='{line}' fill='none' stroke='#65a30d' stroke-width='2.5'/>{dots}</svg>"
    )


def render(session: Session, real: StatsResult, everything: StatsResult) -> str:
    s = real.stats
    weak = []
    for i, w in enumerate(s.weak_points, 1):
        diagrams = "".join(_diagram(session, e) for e in w.examples[:3])
        weak.append(
            f"<article><h3>{i}. {html.escape(w.title)}</h3><p>{html.escape(w.text)}</p>"
            f"<p class='muted'>{html.escape(w.advice)}</p>"
            f"<p class='muted'>Coste: {w.cost:.1f} puntos de probabilidad de ganar por partida "
            f"(criterio de orden) · filtro de entrenamiento: <code>{w.train or '—'}</code></p>"
            f"<div class='boards'>{diagrams}</div>{_examples(w.examples)}</article>"
        )
    phases = "".join(
        f"<tr><td>{p.label}</td><td>{p.per10:.2f}</td><td>{p.errors}</td><td>{p.moves}</td>"
        f"<td>{_examples(p.examples, 3)}</td></tr>"
        for p in s.phases
    )
    kinds = "".join(
        f"<tr><td>{html.escape(k.label)}</td><td>{k.count}</td><td>{k.mean_delta:.1f}</td>"
        f"<td>{_examples(k.examples, 3)}</td></tr>"
        for k in s.kinds
    )
    openings = "".join(
        f"<tr class='{'worst' if o.worst else ''}'><td>{'Blancas' if o.color == 'white' else 'Negras'}</td>"
        f"<td>{html.escape(o.family)}</td><td>{o.games}</td><td>{o.wins}-{o.draws}-{o.losses}</td>"
        f"<td>{o.score:.0f} %</td><td>{'—' if o.accuracy is None else f'{o.accuracy:.0f}'}</td></tr>"
        for o in s.openings
    )
    t = s.time

    def pct(v: float | None) -> str:
        return "—" if v is None else f"{100 * v:.1f} %"

    warning = (
        ""
        if s.enough
        else f"<p class='warn'>Son pocas para sacar conclusiones fiables (al menos {s.min_games}).</p>"
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estadísticas · Fase 6b</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px;
  background: #fafaf9; color: #1c1917; line-height: 1.5; }}
h2 {{ margin-top: 36px; border-bottom: 2px solid #d6d3d1; }}
article {{ background: #fff; border: 1px solid #e7e5e4; border-radius: 10px; padding: 12px 16px;
  margin: 12px 0; }}
.boards {{ display: flex; gap: 12px; flex-wrap: wrap; }}
figure {{ margin: 0; }} figcaption {{ font-size: 12px; color: #57534e; text-align: center; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; background: #fff; }}
td, th {{ border-top: 1px solid #e7e5e4; padding: 4px 8px; text-align: left; vertical-align: top; }}
tr.worst td {{ color: #b91c1c; font-weight: 600; }}
.muted {{ color: #57534e; font-size: 14px; }} .ref {{ color: #a8a29e; font-size: 12px; }}
.warn {{ color: #b45309; font-weight: 600; }}
ul {{ margin: 4px 0; padding-left: 18px; }}
code {{ font-family: ui-monospace, monospace; }}
</style></head><body>
<h1>Estadísticas · Fase 6b</h1>
<p>Filtro por defecto (partidas reales: Lichess, Chess.com y PGN). Basado en
<strong>{s.games}</strong> partidas analizadas de {real.games_finished} terminadas
({real.games_unanalysed} sin analizar). Con las partidas contra el bot serían
{everything.stats.games}.</p>
{warning}
<h2>Tus 3 puntos débiles</h2>
{"".join(weak) or "<p>No destaca ningún punto débil.</p>"}
<h2>Precisión</h2>
<p>Media: <strong>{"—" if s.accuracy_mean is None else f"{s.accuracy_mean:.1f} %"}</strong>
(puntos: cada partida, en orden de fecha; línea: media de las últimas 5).</p>
{_accuracy_svg(s)}
<h2>Errores por fase</h2>
<p class="muted">Errores (?, ?? y ✗) cada 10 jugadas tuyas en esa fase.</p>
<table><tr><th>Fase</th><th>Cada 10</th><th>Errores</th><th>Jugadas</th><th>Posiciones</th></tr>{phases}</table>
<h2>Tipos de error más frecuentes</h2>
<table><tr><th>Tipo</th><th>Veces</th><th>Δ medio</th><th>Posiciones</th></tr>{kinds}</table>
<h2>Errores con poco tiempo</h2>
<p>Partidas con reloj: {t.games_with_clock}. Con poco tiempo: {t.low_errors} errores en
{t.low_moves} jugadas ({pct(t.low_rate)}); con tiempo: {t.normal_errors} en {t.normal_moves}
({pct(t.normal_rate)}). {"<strong>Destaca: punto débil «gestión del tiempo».</strong>" if t.stands_out else "No destaca."}</p>
{_examples(t.examples)}
<h2>Aperturas</h2>
<table><tr><th>Color</th><th>Apertura</th><th>Partidas</th><th>V-T-D</th><th>Puntos</th><th>Precisión</th></tr>{openings}</table>
<p class="muted">En rojo, las peores (al menos 3 partidas y menos del 50 % de los puntos).</p>
</body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Informe de estadísticas (Fase 6b).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    settings = get_settings()
    db = make_db_engine(settings.database_url)
    init_db(db)
    analysis = AnalysisService(
        db, settings, PoolManager(StockfishEngine.start_for_analysis, settings), lambda: None
    )
    insights = InsightService(db, analysis, use_process=False)
    stale = insights.stale()
    for game_id in stale:
        insights.refresh(game_id)
    with Session(db) as session:
        real = load_stats(session, StatsFilters())
        everything = load_stats(session, StatsFilters(include_bot=True))
        if real.stats.games == 0:
            print("No hay partidas reales analizadas en la base.", file=sys.stderr)
        Path(args.out).write_text(render(session, real, everything), encoding="utf-8")
    print(f"{real.stats.games} partidas ({len(stale)} calculadas ahora) → {args.out}")


if __name__ == "__main__":
    main()
