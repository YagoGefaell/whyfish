import pytest

from app.analysis.types import EngineLine, PositionEval
from app.analysis.winprob import (
    game_accuracy,
    move_accuracy,
    position_win,
    volatility_weights,
    win_percent,
)


class TestWinPercent:
    def test_equal_position_is_50(self) -> None:
        assert win_percent(0, None) == 50.0

    def test_symmetric_and_monotonic(self) -> None:
        assert win_percent(100, None) == pytest.approx(100 - win_percent(-100, None))
        assert 50 < win_percent(100, None) < win_percent(300, None) < 100

    def test_lichess_reference_values(self) -> None:
        # 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
        assert win_percent(100, None) == pytest.approx(59.10, abs=0.01)
        assert win_percent(-300, None) == pytest.approx(24.89, abs=0.01)

    def test_clamped_at_1000_cp(self) -> None:
        assert win_percent(5000, None) == win_percent(1000, None)

    def test_mate(self) -> None:
        assert win_percent(None, 3) == 100.0
        assert win_percent(None, -1) == 0.0

    def test_position_win_uses_terminal_or_best_line(self) -> None:
        assert position_win(PositionEval(terminal_win=0.0)) == 0.0
        lines = (EngineLine(("e2e4",), cp=0), EngineLine(("d2d4",), cp=-50))
        assert position_win(PositionEval(lines=lines)) == 50.0


class TestAccuracy:
    def test_no_loss_is_100(self) -> None:
        assert move_accuracy(60, 60) == 100.0
        assert move_accuracy(60, 70) == 100.0

    def test_reference_value(self) -> None:
        # 103.1668 * exp(-0.04354 * 10) - 3.1669 + 1
        assert move_accuracy(60, 50) == pytest.approx(64.58, abs=0.01)

    def test_clamped_to_zero(self) -> None:
        assert move_accuracy(100, 0) == 0.0

    def test_volatility_weights_one_per_move(self) -> None:
        wins = [50, 52, 48, 70, 30, 31, 90, 95]
        weights = volatility_weights(wins)
        assert len(weights) == len(wins) - 1
        assert all(0.5 <= w <= 12 for w in weights)

    def test_game_accuracy_of_perfect_game(self) -> None:
        assert game_accuracy([100, 100, 100], [1, 2, 3]) == pytest.approx(100)

    def test_game_accuracy_punishes_a_blunder_more_than_the_mean(self) -> None:
        accuracies = [100, 100, 100, 10]
        result = game_accuracy(accuracies, [1, 1, 1, 1])
        assert result is not None and result < sum(accuracies) / 4

    def test_no_moves(self) -> None:
        assert game_accuracy([], []) is None
