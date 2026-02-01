"""Unit tests for PerformanceTracker.

Tests performance tracking, metrics calculation, and benchmark comparison.
"""

from datetime import date, timedelta

import pytest

from src.monitoring.performance_tracker import DailyPerformance, PerformanceTracker


class TestDailyPerformance:
    """Tests for DailyPerformance dataclass."""

    def test_initialization(self):
        """Test DailyPerformance initialization."""
        perf = DailyPerformance(
            date=date(2024, 1, 1),
            portfolio_value=102000.0,
            cash=50000.0,
            positions_value=52000.0,
            daily_pnl=2000.0,
            daily_return=0.02,
        )

        assert perf.date == date(2024, 1, 1)
        assert perf.portfolio_value == 102000.0
        assert perf.cash == 50000.0
        assert perf.positions_value == 52000.0
        assert perf.daily_pnl == 2000.0
        assert perf.daily_return == 0.02


class TestPerformanceTracker:
    """Tests for PerformanceTracker."""

    def test_initialization(self):
        """Test PerformanceTracker initialization."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        assert tracker.initial_capital == 100000.0
        assert tracker.risk_free_rate == 0.04
        assert len(tracker.history) == 0
        assert tracker.peak_value == 100000.0

    def test_initialization_custom_risk_free_rate(self):
        """Test initialization with custom risk-free rate."""
        tracker = PerformanceTracker(
            initial_capital=100000.0,
            risk_free_rate=0.05,
        )

        assert tracker.risk_free_rate == 0.05

    def test_record_daily_performance_first_day(self):
        """Test recording first day of performance."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        perf = tracker.record_daily_performance(
            date=date(2024, 1, 1),
            portfolio_value=102000.0,
            cash=50000.0,
            positions_value=52000.0,
        )

        assert perf.portfolio_value == 102000.0
        assert perf.daily_pnl == 2000.0  # 102000 - 100000
        assert perf.daily_return == pytest.approx(0.02)  # 2000 / 100000
        assert perf.cumulative_return == pytest.approx(0.02)
        assert perf.max_drawdown == 0.0  # No drawdown on first day at peak

    def test_record_daily_performance_multiple_days(self):
        """Test recording multiple days of performance."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Day 1: +2%
        perf1 = tracker.record_daily_performance(
            date=date(2024, 1, 1),
            portfolio_value=102000.0,
            cash=50000.0,
            positions_value=52000.0,
        )

        # Day 2: +1% from day 1
        perf2 = tracker.record_daily_performance(
            date=date(2024, 1, 2),
            portfolio_value=103020.0,
            cash=51000.0,
            positions_value=52020.0,
        )

        assert perf2.daily_pnl == pytest.approx(1020.0)  # 103020 - 102000
        assert perf2.daily_return == pytest.approx(0.01)  # 1020 / 102000
        assert perf2.cumulative_return == pytest.approx(0.0302)  # (103020 - 100000) / 100000

    def test_peak_tracking(self):
        """Test peak value tracking for drawdown calculation."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Day 1: New peak
        tracker.record_daily_performance(
            date=date(2024, 1, 1),
            portfolio_value=105000.0,
            cash=50000.0,
            positions_value=55000.0,
        )

        assert tracker.peak_value == 105000.0
        assert tracker.peak_date == date(2024, 1, 1)

        # Day 2: Decline (no new peak)
        perf2 = tracker.record_daily_performance(
            date=date(2024, 1, 2),
            portfolio_value=103000.0,
            cash=50000.0,
            positions_value=53000.0,
        )

        assert tracker.peak_value == 105000.0  # Peak unchanged
        assert perf2.max_drawdown == pytest.approx(-0.01905, abs=0.001)  # (103000 - 105000) / 105000

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation with sufficient data."""
        tracker = PerformanceTracker(
            initial_capital=100000.0,
            risk_free_rate=0.04,
        )

        # Generate 25 days of performance data (need >20 for Sharpe)
        for i in range(25):
            # Simulate 0.1% daily return
            value = 100000.0 * (1.001 ** (i + 1))
            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=value,
                cash=50000.0,
                positions_value=value - 50000.0,
            )

        latest = tracker.get_latest_performance()
        assert latest.sharpe_ratio is not None
        assert latest.sharpe_ratio > 0  # Positive returns should give positive Sharpe

    def test_sharpe_ratio_not_calculated_insufficient_data(self):
        """Test Sharpe ratio not calculated with insufficient data."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Only 10 days of data
        for i in range(10):
            value = 100000.0 * (1.001 ** (i + 1))
            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=value,
                cash=50000.0,
                positions_value=value - 50000.0,
            )

        latest = tracker.get_latest_performance()
        assert latest.sharpe_ratio is None

    def test_get_performance_metrics_empty(self):
        """Test getting metrics with no data."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        metrics = tracker.get_performance_metrics()

        assert metrics["total_return"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["max_drawdown"] == 0.0
        assert metrics["num_days"] == 0

    def test_get_performance_metrics_with_data(self):
        """Test getting comprehensive performance metrics."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Generate 30 days of data
        for i in range(30):
            # Alternate between gains and losses
            return_pct = 0.01 if i % 2 == 0 else -0.005
            value = tracker.initial_capital if i == 0 else tracker.history[-1].portfolio_value
            new_value = value * (1 + return_pct)

            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=new_value,
                cash=50000.0,
                positions_value=new_value - 50000.0,
            )

        metrics = tracker.get_performance_metrics()

        assert metrics["num_days"] == 30
        assert "total_return" in metrics
        assert "daily_returns_mean" in metrics
        assert "daily_returns_std" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics
        assert "total_pnl" in metrics

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # 7 positive days, 3 negative days
        for i in range(10):
            return_pct = 0.01 if i < 7 else -0.01
            value = tracker.initial_capital if i == 0 else tracker.history[-1].portfolio_value
            new_value = value * (1 + return_pct)

            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=new_value,
                cash=50000.0,
                positions_value=new_value - 50000.0,
            )

        metrics = tracker.get_performance_metrics()
        assert metrics["win_rate"] == 0.7  # 7 out of 10

    def test_get_equity_curve(self):
        """Test getting equity curve as DataFrame."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        for i in range(5):
            value = 100000.0 + (i * 1000)
            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=value,
                cash=50000.0,
                positions_value=value - 50000.0,
            )

        equity_curve = tracker.get_equity_curve()

        assert len(equity_curve) == 5
        assert "portfolio_value" in equity_curve.columns
        assert "cumulative_return" in equity_curve.columns

    def test_get_returns_series(self):
        """Test getting returns series."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        for i in range(5):
            value = 100000.0 * (1.01 ** (i + 1))
            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=value,
                cash=50000.0,
                positions_value=value - 50000.0,
            )

        returns = tracker.get_returns_series()

        assert len(returns) == 5
        assert all(returns > 0)  # All positive returns

    def test_get_latest_performance(self):
        """Test getting latest performance snapshot."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # No data
        assert tracker.get_latest_performance() is None

        # Add data
        tracker.record_daily_performance(
            date=date(2024, 1, 1),
            portfolio_value=102000.0,
            cash=50000.0,
            positions_value=52000.0,
        )

        latest = tracker.get_latest_performance()
        assert latest is not None
        assert latest.portfolio_value == 102000.0

    def test_get_drawdown_series(self):
        """Test getting drawdown series over time."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Day 1: +5%
        tracker.record_daily_performance(
            date=date(2024, 1, 1),
            portfolio_value=105000.0,
            cash=50000.0,
            positions_value=55000.0,
        )

        # Day 2: -3% from peak
        tracker.record_daily_performance(
            date=date(2024, 1, 2),
            portfolio_value=101850.0,
            cash=50000.0,
            positions_value=51850.0,
        )

        dd_series = tracker.get_drawdown_series()

        assert len(dd_series) == 2
        assert "peak_value" in dd_series.columns
        assert "drawdown_pct" in dd_series.columns

        # Day 1 should have 0% drawdown (at peak)
        assert dd_series.iloc[0]["drawdown_pct"] == 0.0

        # Day 2 should have negative drawdown
        assert dd_series.iloc[1]["drawdown_pct"] < 0.0

    def test_compare_to_benchmark(self):
        """Test benchmark comparison."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Portfolio returns
        for i in range(5):
            value = 100000.0 * (1.02 ** (i + 1))  # +2% daily
            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=value,
                cash=50000.0,
                positions_value=value - 50000.0,
            )

        # Benchmark returns (lower than portfolio)
        benchmark_returns = {
            date(2024, 1, 1): 0.01,  # +1% daily
            date(2024, 1, 2): 0.01,
            date(2024, 1, 3): 0.01,
            date(2024, 1, 4): 0.01,
            date(2024, 1, 5): 0.01,
        }

        comparison = tracker.compare_to_benchmark(benchmark_returns)

        assert "portfolio_return" in comparison
        assert "benchmark_return" in comparison
        assert "alpha" in comparison
        assert "tracking_error" in comparison

        # Portfolio should outperform benchmark (alpha > 0)
        assert comparison["alpha"] > 0

    def test_reset(self):
        """Test resetting tracker."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        # Add some data
        for i in range(5):
            tracker.record_daily_performance(
                date=date(2024, 1, 1) + timedelta(days=i),
                portfolio_value=102000.0,
                cash=50000.0,
                positions_value=52000.0,
            )

        # Reset
        tracker.reset()

        assert len(tracker.history) == 0
        assert tracker.peak_value == 100000.0
        assert tracker.peak_date is None

    def test_reset_with_new_capital(self):
        """Test resetting with new initial capital."""
        tracker = PerformanceTracker(initial_capital=100000.0)

        tracker.reset(new_initial_capital=200000.0)

        assert tracker.initial_capital == 200000.0
        assert tracker.peak_value == 200000.0
