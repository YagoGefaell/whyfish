# ruff: noqa: E501, RUF001  (HTML template: long lines and typographic characters)
"""Training report (phase 6c acceptance): a self-contained HTML file.

    DATABASE_URL=sqlite:////tmp/x.db uv run python -m app.training.report --out report.html

Creates the exercises of the analysed games (as the app does), picks the first ones the way
the daily session does (real games first: due, then new ones with priority for the weak
points' error kinds; games against the bot only fill the slots left) and shows each with its position, wording, context, solution, kind and why it is
included; plus examples of positions excluded as decided or without a clear solution.
"""

import argparse
import html
import re
from datetime import date
from pathlib import Path

import chess
import chess.svg
from sqlmodel import Session, select

from app.analysis.book import default_book
from app.analysis.classify import equal_moves
from app.analysis.review import GameReview, build_review
from app.analysis.runner import AnalysisService
from app.analysis.types import PositionEval
from app.analysis.winprob import line_score, line_win, position_win
from app.api.training import PROMPT, _context
from app.api.why import best_explanation
from app.config import get_settings
from app.db import init_db, make_db_engine
from app.engine.pool import PoolManager
from app.engine.stockfish import StockfishEngine
from app.models.training import TrainingItem
from app.play.service import GameRepository, LoadedGame
from app.stats.aggregate import KIND_LABEL
from app.stats.insights import InsightService
from app.training.logic import Filter, pick_session
from app.training.service import TrainingService

CLASS = {"blunder": "?? Grave error", "mistake": "? Error", "miss": "✗ Oportunidad perdida"}
PHASE = {"opening": "apertura", "middlegame": "medio juego", "endgame": "final"}


def _marked(text: str) -> str:
    return re.sub(r"\[\[([^\[\]]+)\]\]", r"<b>\1</b>", html.escape(text))


class Report:
    def __init__(self, session: Session, analysis: AnalysisService) -> None:
        self.session = session
        self.analysis = analysis
        self.repo = GameRepository(session)
        self.book = default_book()
        self._cache: dict[int, tuple[LoadedGame, list[PositionEval], GameReview]] = {}

    def data(self, game_id: int) -> tuple[LoadedGame, list[PositionEval], GameReview]:
        if game_id not in self._cache:
            loaded = self.repo.load(game_id)
            _, evals = self.analysis.evaluations(game_id)
            review = build_review(
                loaded.game.initial_fen,
                [m.uci for m in loaded.moves],
                evals,
                loaded.game.player_color.chess_color,
                self.book,
            )
            self._cache[game_id] = (loaded, evals, review)
        return self._cache[game_id]

    def board(self, item: TrainingItem) -> tuple[chess.Board, str]:
        loaded, _, _ = self.data(item.game_id)
        board = chess.Board(loaded.game.initial_fen)
        for m in loaded.moves[: item.ply]:
            board.push_uci(m.uci)
        last = loaded.moves[item.ply - 1].uci if item.ply > 0 else None
        lastmove = chess.Move.from_uci(last) if last else None
        svg = chess.svg.board(
            board,
            orientation=loaded.game.player_color.chess_color,
            lastmove=lastmove if item.classification == "miss" else None,
            size=240,
        )
        return board, svg

    def article(
        self, n: int, item: TrainingItem, weak: list[str], reason: str | None = None
    ) -> str:
        loaded, evals, review = self.data(item.game_id)
        board, svg = self.board(item)
        ctx = _context(loaded.game, board)
        moved = review.moves[item.ply]
        lines = evals[item.ply].lines
        best = lines[0]
        best_san = board.san(chess.Move.from_uci(best.move))
        alternatives = [board.san(chess.Move.from_uci(u)) for u in equal_moves(evals[item.ply])]
        explanation = best_explanation(loaded, evals, review, item.ply)
        kind = KIND_LABEL.get(item.error_kind or "", item.error_kind or "—")
        side = "blancas" if ctx.color.value == "white" else "negras"
        prev = 100.0 - position_win(evals[item.ply - 1]) if item.ply > 0 else moved.win_before
        prompt = PROMPT["miss" if item.classification == "miss" else "error"]
        why_in = [
            f"{CLASS.get(item.classification, item.classification)} (−{moved.delta:.0f} puntos de probabilidad de ganar); tipo «{kind}», {PHASE.get(item.phase, item.phase)}"
            + (" — <b>uno de tus puntos débiles</b>" if item.error_kind in weak else ""),
            f"No decidida: tu probabilidad antes del último movimiento del rival era {prev:.0f} % y ahora {moved.win_before:.0f} %",
            "Solución clara: ninguna otra jugada igual de buena"
            if not alternatives
            else f"Solución clara: una alternativa igual de buena ({', '.join(alternatives)}), que también cuenta como acierto",
        ]
        if item.low_time:
            why_in.append("Cometido con poco tiempo en el reloj")
        if reason == "decided":
            why_in = [
                f"<b>Excluido: partida decidida.</b> Tu probabilidad antes del movimiento del rival era {prev:.0f} % y en esta posición {moved.win_before:.0f} %: ya estaba ganada o perdida antes de esta jugada."
            ]
        elif reason == "unclear":
            alts = ", ".join(
                f"{board.san(chess.Move.from_uci(ln.move))} ({line_win(ln):.0f} %, {line_score(ln):+d} cp)"
                for ln in lines
            )
            why_in = [
                f"<b>Excluido: solución no clara.</b> Varias jugadas distintas son igual de buenas (Δ < 1): {html.escape(alts)}."
            ]
        sol = (
            f"<p><b>Solución:</b> {html.escape(best_san)}"
            + (f" (también valía {html.escape(', '.join(alternatives))})" if alternatives else "")
            + "</p>"
        )
        expl = (
            f"<p class='muted'>{_marked(explanation.text)}</p>"
            if explanation and explanation.text
            else ""
        )
        return (
            f"<article><div class='board'>{svg}</div><div class='text'>"
            f"<h3>{n}. {html.escape(prompt)}</h3>"
            f"<p class='ctx'>Partida contra {html.escape(ctx.opponent)} ({html.escape(ctx.origin)}"
            f"{', ' + ctx.pace if ctx.pace else ''}), jugada {ctx.move_number}, juegas con {side}.</p>"
            f"<p>Lo que jugaste: <b>{html.escape(moved.san)}</b> · {CLASS.get(item.classification, '')}</p>"
            f"{sol}{expl}<ul>{''.join(f'<li>{w}</li>' for w in why_in)}</ul></div></article>"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Informe de entrenamiento (Fase 6c).")
    parser.add_argument("--out", required=True)
    parser.add_argument("--size", type=int, default=10)
    args = parser.parse_args()
    settings = get_settings()
    db = make_db_engine(settings.database_url)
    init_db(db)
    analysis = AnalysisService(
        db, settings, PoolManager(StockfishEngine.start_for_analysis, settings), lambda: None
    )
    insights = InsightService(db, analysis, use_process=False)
    for game_id in insights.stale():
        insights.refresh(game_id)
    training = TrainingService(db, analysis)
    created = training.sync_items()
    weak = training.weak_kinds()
    s = training.settings()
    weak_new = round(s.weak_new * args.size / max(1, s.session_size))
    ids = pick_session(
        training.candidates(),
        date.today(),
        args.size,
        weak,
        weak_new,
        Filter(),
        s.include_bullet,
        s.include_bot,
    )
    counts = training.counts(date.today())
    with Session(db) as session:
        items = {i.id: i for i in session.exec(select(TrainingItem)).all()}
        report = Report(session, analysis)
        chosen = "".join(report.article(n, items[i], weak) for n, i in enumerate(ids, 1))
        excluded = []
        for reason in ("decided", "unclear"):
            rows = [i for i in items.values() if i.excluded == reason][:3]
            excluded += [report.article(n, i, weak, reason) for n, i in enumerate(rows, 1)]
    weak_txt = ", ".join(KIND_LABEL.get(k, k) for k in weak) or "—"
    page = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrenamiento · Fase 6c</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px;
  background: #fafaf9; color: #1c1917; line-height: 1.5; }}
h2 {{ margin-top: 36px; border-bottom: 2px solid #d6d3d1; }}
article {{ display: flex; gap: 18px; flex-wrap: wrap; background: #fff; border: 1px solid #e7e5e4;
  border-radius: 10px; padding: 14px; margin: 14px 0; }}
.board {{ flex: 0 0 240px; }} .text {{ flex: 1 1 360px; min-width: 0; }}
.ctx {{ color: #57534e; margin-top: 0; }} .muted {{ color: #44403c; }}
h3 {{ margin: 0 0 6px; }}
</style></head><body>
<h1>Entrenamiento · Fase 6c</h1>
<p>Ejercicios creados de tus errores (?, ?? y ✗) en partidas analizadas: {len(items)} posiciones
({created} creadas ahora). Disponibles: {counts["new"]} nuevos y {counts["due"]} para repasar hoy;
fuera: {counts["decided"]} con la partida ya decidida, {counts["unclear"]} sin una solución clara,
{counts["bullet"]} de bala (excluidas por defecto){f", {counts['bot']} contra el bot (desactivadas)" if counts["bot"] else ""}. Tus puntos débiles: {html.escape(weak_txt)}.</p>
<p>Abajo, los {len(ids)} primeros ejercicios tal como los elegiría la sesión diaria (con {args.size}
ejercicios: primero los de tus partidas reales —Chess.com, Lichess, PGN—, hasta {weak_new} nuevos de
tus puntos débiles y el resto los errores más recientes; los de partidas contra el bot solo
completan los huecos{"" if s.include_bot else " y ahora están desactivados"}). El
tablero es la posición que verías (orientada a tu color); en las ✗ se resalta la última jugada del
rival. La solución y la explicación solo se muestran al resolverlo.</p>
<h2>Ejercicios</h2>
{chosen or "<p>No hay ejercicios.</p>"}
<h2>Ejemplos de posiciones excluidas</h2>
{"".join(excluded) or "<p>Ninguna.</p>"}
</body></html>
"""
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{len(ids)} ejercicios, {len(excluded)} exclusiones de ejemplo → {args.out}")


if __name__ == "__main__":
    main()
