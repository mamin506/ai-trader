"""Performance tracking for paper trading.

This module tracks portfolio performance metrics including P&L, returns,
Sharpe ratio, drawdown, and benchmark comparison.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class DailyPerformance:
    """Daily performance snapshot.

    Attributes:
        date: Trading date
        portfolio_value: End-of-day portfolio value
        cash: Cash balance
        positions_value: Total value of positions
        daily_pnl: Daily profit/loss in dollars
        daily_return: Daily return percentage
        cumulative_return: Cumulative return from start
        benchmark_return: Benchmark daily return (e.g., SPY)
        sharpe_ratio: Rolling Sharpe ratio (if enough data)
        max_drawdown: Maximum drawdown from peak
    """

    date: date
    portfolio_value: float
    cash: float
    positions_value: float
    daily_pnl: float = 0.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    benchmark_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: float = 0.0


class PerformanceTracker:
    """Tracks portfolio performance over time.

    Maintains historical performance data and calculates various metrics
    including returns, Sharpe ratio, drawdown, and benchmark comparison.

    Example:
        >>> tracker = PerformanceTracker(initial_capital=100000.0)
        >>> tracker.record_daily_performance(
        ...     date=date(2024, 1, 1),
        ...     portfolio_value=102000.0,
        ...     cash=50000.0,
        ...     positions_value=52000.0,
        ... )
        >>> metrics = tracker.get_performance_metrics()
        >>> print(f"Total return: {metrics['total_return']:.2%}")
    """

    def __init__(
        self,
        initial_capital: float,
        risk_free_rate: float = 0.04,  # 4% annual risk-free rate
    ):
        """Initialize performance tracker.

        Args:
            initial_capital: Starting portfolio value
            risk_free_rate: Annual risk-free rate for Sharpe ratio (default 4%)
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.daily_rf_rate = (1 + risk_free_rate) ** (1 / 252) - 1  # Daily rate

        # Performance history
        self.history: List[DailyPerformance] = []

        # Peak tracking for drawdown
        self.peak_value = initial_capital
        self.peak_date: Optional[date] = None

    def record_daily_performance(
        self,
        date: date,
        portfolio_value: float,
        cash: float,
        positions_value: float,
        benchmark_return: Optional[float] = None,
    ) -> DailyPerformance:
        """Record end-of-day performance snapshot.

        Args:
            date: Trading date
            portfolio_value: Total portfolio value
            cash: Cash balance
            positions_value: Total value of positions
            benchmark_return: Benchmark daily return (optional)

        Returns:
            DailyPerformance object with calculated metrics
        """
        # Calculate daily P&L and return
        if self.history:
            prev_value = self.history[-1].portfolio_value
            daily_pnl = portfolio_value - prev_value
            daily_return = daily_pnl / prev_value if prev_value > 0 else 0.0
        else:
            daily_pnl = portfolio_value - self.initial_capital
            daily_return = daily_pnl / self.initial_capital if self.initial_capital > 0 else 0.0

        # Calculate cumulative return
        cumulative_return = (
            (portfolio_value - self.initial_capital) / self.initial_capital
            if self.initial_capital > 0
            else 0.0
        )

        # Update peak and calculate drawdown
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
            self.peak_date = date

        max_drawdown = (
            (portfolio_value - self.peak_value) / self.peak_value
            if self.peak_value > 0
            else 0.0
        )

        # Calculate Sharpe ratio (if enough data)
        sharpe_ratio = None
        if len(self.history) >= 20:  # Need at least 20 days
            sharpe_ratio = self._calculate_sharpe_ratio()

        # Create performance record
        perf = DailyPerformance(
            date=date,
            portfolio_value=portfolio_value,
            cash=cash,
            positions_value=positions_value,
            daily_pnl=daily_pnl,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            benchmark_return=benchmark_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
        )

        self.history.append(perf)
        return perf

    def _calculate_sharpe_ratio(self, window: int = 252) -> float:
        """Calculate Sharpe ratio using recent returns.

        Args:
            window: Number of days to use (default 252 = 1 year)

        Returns:
            Annualized Sharpe ratio
        """
        if len(self.history) < 2:
            return 0.0

        # Get recent returns
        recent_history = self.history[-window:]
        returns = [perf.daily_return for perf in recent_history]

        # Calculate excess returns (return - risk-free rate)
        excess_returns = [r - self.daily_rf_rate for r in returns]

        # Calculate Sharpe ratio
        mean_excess = sum(excess_returns) / len(excess_returns)

        if len(excess_returns) < 2:
            return 0.0

        variance = sum((r - mean_excess) ** 2 for r in excess_returns) / (len(excess_returns) - 1)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Annualize
        sharpe = (mean_excess / std_dev) * (252 ** 0.5)
        return sharpe

    def get_performance_metrics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        """Get comprehensive performance metrics.

        Args:
            start_date: Start date for metrics (optional, default: all)
            end_date: End date for metrics (optional, default: all)

        Returns:
            Dict with performance metrics
        """
        if not self.history:
            return {
                "total_return": 0.0,
                "daily_returns_mean": 0.0,
                "daily_returns_std": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "num_days": 0,
            }

        # Filter history by date range
        history = self.history
        if start_date:
            history = [h for h in history if h.date >= start_date]
        if end_date:
            history = [h for h in history if h.date <= end_date]

        if not history:
            return {
                "total_return": 0.0,
                "daily_returns_mean": 0.0,
                "daily_returns_std": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "num_days": 0,
            }

        # Calculate metrics
        latest = history[-1]
        returns = [h.daily_return for h in history]
        pnls = [h.daily_pnl for h in history]

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns) if len(returns) > 1 else 0.0
        std_return = variance ** 0.5

        # Win rate (percentage of positive return days)
        positive_days = sum(1 for r in returns if r > 0)
        win_rate = positive_days / len(returns) if returns else 0.0

        # Max drawdown across the period
        max_dd = min([h.max_drawdown for h in history])

        return {
            "total_return": latest.cumulative_return,
            "daily_returns_mean": mean_return,
            "daily_returns_std": std_return,
            "sharpe_ratio": latest.sharpe_ratio if latest.sharpe_ratio else 0.0,
            "max_drawdown": max_dd,
            "total_pnl": sum(pnls),
            "win_rate": win_rate,
            "num_days": len(history),
            "current_value": latest.portfolio_value,
            "peak_value": self.peak_value,
            "peak_date": self.peak_date.isoformat() if self.peak_date else None,
        }

    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame.

        Returns:
            DataFrame with columns: date, portfolio_value, cumulative_return
        """
        if not self.history:
            return pd.DataFrame(columns=["date", "portfolio_value", "cumulative_return"])

        data = {
            "date": [h.date for h in self.history],
            "portfolio_value": [h.portfolio_value for h in self.history],
            "cumulative_return": [h.cumulative_return for h in self.history],
        }

        df = pd.DataFrame(data)
        df.set_index("date", inplace=True)
        return df

    def get_returns_series(self) -> pd.Series:
        """Get daily returns as pandas Series.

        Returns:
            Series with date index and daily returns
        """
        if not self.history:
            return pd.Series(dtype=float)

        data = {h.date: h.daily_return for h in self.history}
        return pd.Series(data)

    def get_latest_performance(self) -> Optional[DailyPerformance]:
        """Get most recent performance snapshot.

        Returns:
            Latest DailyPerformance or None if no history
        """
        return self.history[-1] if self.history else None

    def get_drawdown_series(self) -> pd.DataFrame:
        """Get drawdown series over time.

        Returns:
            DataFrame with columns: date, portfolio_value, peak_value, drawdown_pct
        """
        if not self.history:
            return pd.DataFrame(columns=["date", "portfolio_value", "peak_value", "drawdown_pct"])

        data = []
        running_peak = self.initial_capital

        for h in self.history:
            running_peak = max(running_peak, h.portfolio_value)
            drawdown_pct = (
                (h.portfolio_value - running_peak) / running_peak
                if running_peak > 0
                else 0.0
            )

            data.append({
                "date": h.date,
                "portfolio_value": h.portfolio_value,
                "peak_value": running_peak,
                "drawdown_pct": drawdown_pct,
            })

        df = pd.DataFrame(data)
        df.set_index("date", inplace=True)
        return df

    def compare_to_benchmark(
        self,
        benchmark_returns: Dict[date, float],
    ) -> Dict:
        """Compare performance to benchmark.

        Args:
            benchmark_returns: Dict mapping date -> daily return

        Returns:
            Dict with comparison metrics
        """
        if not self.history:
            return {
                "portfolio_return": 0.0,
                "benchmark_return": 0.0,
                "alpha": 0.0,
                "tracking_error": 0.0,
            }

        # Calculate portfolio cumulative return
        portfolio_return = self.history[-1].cumulative_return

        # Calculate benchmark cumulative return
        benchmark_cum_return = 0.0
        for h in self.history:
            if h.date in benchmark_returns:
                benchmark_cum_return = (1 + benchmark_cum_return) * (1 + benchmark_returns[h.date]) - 1

        # Calculate alpha (excess return over benchmark)
        alpha = portfolio_return - benchmark_cum_return

        # Calculate tracking error (volatility of excess returns)
        excess_returns = []
        for h in self.history:
            if h.date in benchmark_returns:
                excess = h.daily_return - benchmark_returns[h.date]
                excess_returns.append(excess)

        if excess_returns:
            mean_excess = sum(excess_returns) / len(excess_returns)
            variance = sum((r - mean_excess) ** 2 for r in excess_returns) / len(excess_returns)
            tracking_error = variance ** 0.5
        else:
            tracking_error = 0.0

        return {
            "portfolio_return": portfolio_return,
            "benchmark_return": benchmark_cum_return,
            "alpha": alpha,
            "tracking_error": tracking_error,
            "num_days": len(self.history),
        }

    def reset(self, new_initial_capital: Optional[float] = None) -> None:
        """Reset performance tracker.

        Args:
            new_initial_capital: New starting capital (optional)
        """
        if new_initial_capital is not None:
            self.initial_capital = new_initial_capital

        self.history = []
        self.peak_value = self.initial_capital
        self.peak_date = None
