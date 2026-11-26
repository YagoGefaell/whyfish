"""Assemble a game review from engine evaluations: classified moves, summaries, key moments."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.analysis.book import Opening, OpeningBook
from app.analysis.classify import MoveInput, classify, equal_moves
from app.analysis.types import Classification, PositionEval
from app.analysis.winprob import game_accuracy, position_win, volatility_weights
from app.config import THRESHOLDS, ClassificationThresholds

C = Classification
# Plies of SAN shown for the best line and for the refutation of the played move.
LINE_PLIES = 8


@dataclass(frozen=True)
class WhiteEval:
    """Evaluation of a position from white's point of view (for the eval bar and graph)."""

    win: float
    cp: int | None
    mate: int | None


@dataclass(frozen=True)
class MoveReview:
    ply: int
    color: chess.Color
    uci: str
    san: str
    classification: Classification
    win_before: float
    win_after: float
    delta: float
    accuracy: float
    best_uci: str | None
    best_san: str | None
    best_line: tuple[str, ...]  # SAN, from the position before the move
    played_line: tuple[str, ...]  # SAN, the engine's best continuation after the played move
    # Other moves as good as the best one (SPEC §3: Δ < equal_max_delta): UCI and SAN.
    equal_best: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PlayerSummary:
    accuracy: float | None
    counts: dict[Classification, int]


@dataclass(frozen=True)
class GameReview:
    moves: list[MoveReview]
    white: PlayerSummary
    black: PlayerSummary
    key_moments: list[int]  # plies, in game order
    evals: list[WhiteEval]  # one per position: start + after each move
    opening: Opening | None


def build_review(
    initial_fen: str,
    ucis: Sequence[str],
    evals: Sequence[PositionEval],
    perspective: chess.Color,
    book: OpeningBook | None,
    t: ClassificationThresholds = THRESHOLDS,
) -> GameReview:
    """`evals[i]` is the evaluation of the position before move i; len(evals) == len(ucis) + 1.

    `perspective` is the user's color: key moments are only taken from that side's moves.
    """
    if len(evals) != len(ucis) + 1:
        raise ValueError("need one evaluation per position")
    board = chess.Board(initial_fen)
    moves: list[MoveReview] = []
    white_evals = [_white_eval(board, evals[0])]
    opening: Opening | None = None
    previous: Classification | None = None

    for ply, uci in enumerate(ucis):
        move = chess.Move.from_uci(uci)
        before, after = evals[ply], evals[ply + 1]
        best = before.lines[0] if before.lines else None
        san = board.san(move)
        best_line = _san_line(board, best.moves) if best else ()

        after_board = board.copy()
        after_board.push(move)
        found = book.lookup(after_board) if book else None
        if found:
            opening = found

        verdict = classify(
            MoveInput(
                board=board,
                move=move,
                before=before,
                after=after,
                in_book=found is not None,
                previous=previous,
            ),
            t,
        )
        moves.append(
            MoveReview(
                ply=ply,
                color=board.turn,
                uci=uci,
                san=san,
                classification=verdict.classification,
                win_before=verdict.win_before,
                win_after=verdict.win_after,
                delta=verdict.delta,
                accuracy=verdict.accuracy,
                best_uci=best.move if best else None,
                best_san=best_line[0] if best_line else None,
                best_line=best_line,
                played_line=_san_line(after_board, after.lines[0].moves) if after.lines else (),
                equal_best=tuple(
                    (u, board.san(chess.Move.from_uci(u))) for u in equal_moves(before, t)
                ),
            )
        )
        previous = verdict.classification
        board = after_board
        white_evals.append(_white_eval(board, after))

    weights = volatility_weights([e.win for e in white_evals])
    return GameReview(
        moves=moves,
        white=_summary(moves, weights, chess.WHITE),
        black=_summary(moves, weights, chess.BLACK),
        key_moments=key_moments(moves, perspective, t),
        evals=white_evals,
        opening=opening,
    )


ERRORS = (C.INACCURACY, C.MISTAKE, C.BLUNDER, C.MISS)
HIGHLIGHTS = (C.GREAT, C.BRILLIANT)


def key_moments(
    moves: Sequence[MoveReview], perspective: chess.Color, t: ClassificationThresholds = THRESHOLDS
) -> list[int]:
    """SPEC §3.4: the user's errors by Δ (Δ >= min), then their ! / !! moves. Up to N plies."""
    own = [m for m in moves if m.color == perspective]
    errors = sorted(
        (m for m in own if m.classification in ERRORS and m.delta >= t.key_moment_min_delta),
        key=lambda m: (-m.delta, m.ply),
    )
    highlights = [m for m in own if m.classification in HIGHLIGHTS]
    highlights.sort(key=lambda m: (m.classification != C.BRILLIANT, m.ply))
    chosen = [m.ply for m in (errors + highlights)[: t.key_moments_max]]
    return sorted(chosen)


def _summary(
    moves: Sequence[MoveReview], weights: Sequence[float], color: chess.Color
) -> PlayerSummary:
    own = [(m, w) for m, w in zip(moves, weights, strict=True) if m.color == color]
    counts = Counter(m.classification for m, _ in own)
    return PlayerSummary(
        accuracy=game_accuracy([m.accuracy for m, _ in own], [w for _, w in own]),
        counts={c: counts.get(c, 0) for c in Classification},
    )


def _white_eval(board: chess.Board, evaluation: PositionEval) -> WhiteEval:
    win = position_win(evaluation)
    cp = mate = None
    if evaluation.lines:
        cp, mate = evaluation.lines[0].cp, evaluation.lines[0].mate
    if board.turn == chess.BLACK:
        win = 100.0 - win
        cp = -cp if cp is not None else None
        mate = -mate if mate is not None else None
    return WhiteEval(win=win, cp=cp, mate=mate)


def _san_line(board: chess.Board, ucis: Sequence[str]) -> tuple[str, ...]:
    b = board.copy(stack=False)
    sans: list[str] = []
    for uci in ucis[:LINE_PLIES]:
        try:
            move = chess.Move.from_uci(uci)
            sans.append(b.san(move))
        except ValueError:
            break
        b.push(move)
    return tuple(sans)
