"""Analyse a PGN from the command line (no database): `make analyze PGN=game.pgn`.

Prints every move with its classification, the summary and the time taken. Useful to check
classifications by hand.
"""

import argparse
import asyncio
import io
import sys
import time
from pathlib import Path

import chess
import chess.pgn

from app.analysis.book import default_book
from app.analysis.positions import GamePosition, game_positions
from app.analysis.review import build_review
from app.analysis.runner import evaluate_positions, search_limit
from app.analysis.types import SYMBOLS, Classification, EngineLine, PositionEval
from app.config import get_settings
from app.engine.pool import open_pool
from app.engine.stockfish import StockfishEngine

LABELS = {
    Classification.BOOK: "Teoría",
    Classification.BRILLIANT: "Brillante",
    Classification.GREAT: "Gran jugada",
    Classification.BEST: "Mejor",
    Classification.EXCELLENT: "Excelente",
    Classification.GOOD: "Buena",
    Classification.INACCURACY: "Imprecisión",
    Classification.MISTAKE: "Error",
    Classification.BLUNDER: "Grave error",
    Classification.MISS: "Oportunidad perdida",
}


def move_number(ply: int) -> str:
    return f"{ply // 2 + 1}{'.' if ply % 2 == 0 else '…'}"


async def run(args: argparse.Namespace, pgn_text: str) -> int:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        print("No se encontró ninguna partida en el PGN.", file=sys.stderr)
        return 1
    initial_fen = game.board().fen()
    ucis = [m.uci() for m in game.mainline_moves()]

    overrides: dict[str, object] = {}
    if args.time is not None:
        overrides["analysis_time_s"] = args.time
    if args.depth is not None:
        overrides["analysis_depth"] = args.depth
    if args.pool is not None:
        overrides["engine_pool_size"] = args.pool
    settings = get_settings().model_copy(update=overrides)

    positions = game_positions(initial_fen, ucis)
    todo = [p for p in positions if p.terminal is None]
    results: dict[str, tuple[EngineLine, ...]] = {}

    def store(position: GamePosition, lines: tuple[EngineLine, ...]) -> None:
        results[position.key] = lines
        print(f"\r  analizando… {len(results)}/{len(todo)}", end="", file=sys.stderr)

    started = time.monotonic()
    size = max(1, min(settings.engine_pool_size, len(todo)))
    async with open_pool(StockfishEngine.start_for_analysis, settings, size) as pool:
        await evaluate_positions(
            todo, pool, search_limit(settings), settings.analysis_multipv, store
        )
    elapsed = time.monotonic() - started
    print(file=sys.stderr)

    evals = [p.terminal or PositionEval(lines=results[p.key]) for p in positions]
    perspective = chess.WHITE if args.perspective == "white" else chess.BLACK
    review = build_review(initial_fen, ucis, evals, perspective, default_book())

    headers = game.headers
    print(f"{headers.get('White', '?')} - {headers.get('Black', '?')}  {headers.get('Result', '')}")
    if review.opening:
        print(f"Apertura: {review.opening.eco} {review.opening.name}")
    print()
    print(f"{'#':>4}  {'jugada':<8} {'':<3} {'clasificación':<20} {'Δ':>5} {'prec.':>6}  mejor")
    for m in review.moves:
        number = move_number(m.ply)
        marker = "◆" if m.ply in review.key_moments else " "
        best = "" if m.best_uci == m.uci else (m.best_san or "")
        print(
            f"{number:>4}{marker} {m.san:<8} {SYMBOLS[m.classification]:<3} "
            f"{LABELS[m.classification]:<20} {m.delta:>5.1f} {m.accuracy:>6.1f}  {best}"
        )
    print()
    for name, summary in (("Blancas", review.white), ("Negras", review.black)):
        accuracy = f"{summary.accuracy:.1f}" if summary.accuracy is not None else "-"
        counts = ", ".join(f"{LABELS[c]} {n}" for c, n in summary.counts.items() if n)
        print(f"{name}: precisión {accuracy} | {counts}")
    print("Momentos clave (◆):", ", ".join(move_number(p) for p in review.key_moments) or "-")
    print(
        f"\n{len(todo)} posiciones en {elapsed:.1f} s "
        f"({size} motores, {settings.analysis_time_s} s/posición, "
        f"MultiPV {settings.analysis_multipv})"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Analiza la primera partida de un PGN.")
    parser.add_argument("pgn")
    parser.add_argument("--time", type=float, help="segundos por posición")
    parser.add_argument("--depth", type=int, help="profundidad máxima")
    parser.add_argument("--pool", type=int, help="motores en paralelo")
    parser.add_argument("--perspective", choices=["white", "black"], default="white")
    args = parser.parse_args()
    pgn_text = Path(args.pgn).read_text(encoding="utf-8")
    sys.exit(asyncio.run(run(args, pgn_text)))


if __name__ == "__main__":
    main()
