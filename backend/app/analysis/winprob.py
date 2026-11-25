"""Win probability and accuracy (Lichess formulas).

References (lichess-org/lila, modules/analyse and AccuracyPercent.scala):
- win% = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1), with cp clamped to [-1000, 1000];
  mate scores map to 100 / 0.
- move accuracy = 103.1668 * exp(-0.04354 * (win_before - win_after)) - 3.1669, plus a +1
  "uncertainty bonus", clamped to [0, 100]; 100 when the move did not lose win%.
- game accuracy = mean of (volatility-weighted mean, harmonic mean) of the move accuracies,
  where each move's weight is the standard deviation of the win% (white POV) over a sliding
  window of positions, clamped to [0.5, 12]; window size = clamp(positions / 10, 2, 8).
"""

import math
from collections.abc import Sequence

from app.analysis.types import EngineLine, PositionEval

_CP_CLAMP = 1000
_K = 0.00368208


def win_percent(cp: int | None, mate: int | None) -> float:
    """Win% for the side whose point of view the score is given from."""
    if mate is not None:
        return 100.0 if mate > 0 else 0.0
    if cp is None:
        raise ValueError("score needs cp or mate")
    clamped = max(-_CP_CLAMP, min(_CP_CLAMP, cp))
    return 50 + 50 * (2 / (1 + math.exp(-_K * clamped)) - 1)


def line_win(line: EngineLine) -> float:
    return win_percent(line.cp, line.mate)


def position_win(evaluation: PositionEval) -> float:
    """Win% for the side to move: terminal value or best line."""
    if evaluation.terminal_win is not None:
        return evaluation.terminal_win
    if not evaluation.lines:
        raise ValueError("non-terminal position without engine lines")
    return line_win(evaluation.lines[0])


def move_accuracy(win_before: float, win_after: float) -> float:
    """Accuracy (0-100) of a move from the mover's win% before and after it."""
    if win_after >= win_before:
        return 100.0
    raw = 103.1668 * math.exp(-0.04354 * (win_before - win_after)) - 3.1669 + 1
    return max(0.0, min(100.0, raw))


def _stdev(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def volatility_weights(white_wins: Sequence[float]) -> list[float]:
    """One weight per move, from the win% (white POV) of every position (moves + 1 values)."""
    n = len(white_wins)
    if n < 2:
        return []
    size = max(2, min(8, n // 10))
    first = list(white_wins[:size])
    windows = [first] * (size - 2) + [list(white_wins[i : i + size]) for i in range(n - size + 1)]
    return [max(0.5, min(12.0, _stdev(w))) for w in windows[: n - 1]]


def game_accuracy(accuracies: Sequence[float], weights: Sequence[float]) -> float | None:
    """Accuracy of one player. `weights` are the volatility weights of that player's moves."""
    if not accuracies:
        return None
    weighted = sum(a * w for a, w in zip(accuracies, weights, strict=True)) / sum(weights)
    # Harmonic mean; accuracies are floored at 1 so a single 0 doesn't make it undefined.
    harmonic = len(accuracies) / sum(1 / max(a, 1.0) for a in accuracies)
    return (weighted + harmonic) / 2
