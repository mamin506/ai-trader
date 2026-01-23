"""Strategy comparison and analysis tools.

This module provides the StrategyComparator class for comparing the performance
of multiple trading strategies side-by-side.
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np

from src.api.backtest_api import BacktestAPI
from src.strategy.base import Strategy
from src.orchestration.backtest_orchestrator import BacktestResult
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StrategyComparator:
    """Compare performance of multiple trading strategies.

    This class runs backtests for multiple strategies and provides
    side-by-side performance comparison and analysis.

    Example:
        >>> from src.strategy.ma_crossover import MACrossoverStrategy
        >>> from src.strategy.rsi_strategy import RSIStrategy
        >>> from src.analysis import StrategyComparator
        >>>
        >>> # Define strategies to compare
        >>> strategies = [
        ...     ('MA(20/50)', MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})),
        ...     ('RSI(14)', RSIStrategy({'rsi_period': 14, 'oversold_threshold': 30, 'overbought_threshold': 70})),
        ... ]
        >>>
        >>> # Compare
        >>> comparator = StrategyComparator(strategies)
        >>> results = comparator.compare(
        ...     symbols=['AAPL', 'MSFT'],
        ...     start_date='2023-01-01',
        ...     end_date='2024-01-01'
        ... )
        >>> comparator.print_summary()
    """

    def __init__(self, strategies: List[tuple[str, Strategy]]):
        """Initialize strategy comparator.

        Args:
            strategies: List of (name, strategy) tuples
                       Example: [('MA 20/50', MACrossoverStrategy({...}))]
        """
        if not strategies:
            raise ValueError("Must provide at least one strategy")

        self.strategies = strategies
        self.backtest_api = BacktestAPI()
        self.results: Dict[str, BacktestResult] = {}
        self.comparison_df: pd.DataFrame = None

        logger.info("Initialized StrategyComparator with %d strategies", len(strategies))

    def compare(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        rebalance_frequency: str = "weekly",
    ) -> Dict[str, BacktestResult]:
        """Run backtests for all strategies and compare results.

        Args:
            symbols: List of stock symbols to trade
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_capital: Starting capital
            rebalance_frequency: 'daily', 'weekly', or 'monthly'

        Returns:
            Dictionary mapping strategy names to BacktestResult objects
        """
        logger.info(
            "Comparing %d strategies on %d symbols from %s to %s",
            len(self.strategies),
            len(symbols),
            start_date,
            end_date,
        )

        self.results = {}

        for name, strategy in self.strategies:
            logger.info("Running backtest for strategy: %s", name)

            try:
                result = self.backtest_api.run_backtest(
                    strategy=strategy,
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    rebalance_frequency=rebalance_frequency,
                )
                self.results[name] = result

                logger.info(
                    "%s - Return: %.2f%%, Sharpe: %.2f",
                    name,
                    result.total_return * 100,
                    result.sharpe_ratio,
                )

            except Exception as e:
                logger.error("Failed to backtest %s: %s", name, str(e))
                # Store None for failed strategies
                self.results[name] = None

        # Build comparison DataFrame
        self._build_comparison_df()

        return self.results

    def _build_comparison_df(self):
        """Build comparison DataFrame from results."""
        comparison_data = []

        for name, result in self.results.items():
            if result is None:
                # Failed backtest
                comparison_data.append({
                    "Strategy": name,
                    "Total Return (%)": np.nan,
                    "Annualized Return (%)": np.nan,
                    "Sharpe Ratio": np.nan,
                    "Max Drawdown (%)": np.nan,
                    "Num Trades": 0,
                    "Win Rate (%)": 0.0,
                })
            else:
                comparison_data.append({
                    "Strategy": name,
                    "Total Return (%)": result.total_return * 100,
                    "Annualized Return (%)": result.annualized_return * 100,
                    "Sharpe Ratio": result.sharpe_ratio,
                    "Max Drawdown (%)": result.max_drawdown * 100,
                    "Num Trades": result.num_trades,
                    "Win Rate (%)": result.win_rate * 100,
                })

        self.comparison_df = pd.DataFrame(comparison_data)

        # Sort by Sharpe ratio (best first)
        self.comparison_df = self.comparison_df.sort_values(
            "Sharpe Ratio", ascending=False
        ).reset_index(drop=True)

    def get_comparison_table(self) -> pd.DataFrame:
        """Get comparison DataFrame.

        Returns:
            DataFrame with performance metrics for all strategies
        """
        if self.comparison_df is None:
            raise ValueError("Must run compare() first")

        return self.comparison_df.copy()

    def get_best_strategy(self, metric: str = "sharpe_ratio") -> tuple[str, BacktestResult]:
        """Get the best performing strategy based on a metric.

        Args:
            metric: Metric to use ('sharpe_ratio', 'total_return', 'max_drawdown')

        Returns:
            Tuple of (strategy_name, result)
        """
        if self.comparison_df is None:
            raise ValueError("Must run compare() first")

        metric_map = {
            "sharpe_ratio": "Sharpe Ratio",
            "total_return": "Total Return (%)",
            "annualized_return": "Annualized Return (%)",
            "max_drawdown": "Max Drawdown (%)",
        }

        if metric not in metric_map:
            raise ValueError(f"Invalid metric '{metric}'")

        col_name = metric_map[metric]

        if metric == "max_drawdown":
            # For drawdown, less negative is better
            best_idx = self.comparison_df[col_name].abs().idxmin()
        else:
            # For return and Sharpe, higher is better
            best_idx = self.comparison_df[col_name].idxmax()

        best_name = self.comparison_df.loc[best_idx, "Strategy"]
        return best_name, self.results[best_name]

    def print_summary(self):
        """Print formatted comparison summary."""
        if self.comparison_df is None:
            raise ValueError("Must run compare() first")

        print("\n" + "=" * 80)
        print("STRATEGY COMPARISON SUMMARY")
        print("=" * 80)
        print()

        # Format and print comparison table
        print(self.comparison_df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

        print()
        print("-" * 80)

        # Highlight best strategies
        best_sharpe = self.get_best_strategy("sharpe_ratio")
        best_return = self.get_best_strategy("total_return")

        print(f"\n🏆 Best by Sharpe Ratio: {best_sharpe[0]} ({best_sharpe[1].sharpe_ratio:.2f})")
        print(f"💰 Best by Total Return: {best_return[0]} ({best_return[1].total_return*100:.2f}%)")

        # Risk metrics
        print(f"\n📊 Risk Analysis:")
        for name, result in self.results.items():
            if result:
                print(f"  {name}: Max Drawdown = {result.max_drawdown*100:.2f}%")

        print()
        print("=" * 80 + "\n")

    def get_equity_curves(self) -> pd.DataFrame:
        """Get equity curves for all strategies.

        Returns:
            DataFrame with date index and columns for each strategy's equity
        """
        if not self.results:
            raise ValueError("Must run compare() first")

        equity_curves = {}

        for name, result in self.results.items():
            if result and result.equity_curve is not None:
                equity_curves[name] = result.equity_curve["equity"]

        if not equity_curves:
            return pd.DataFrame()

        # Combine into single DataFrame
        equity_df = pd.DataFrame(equity_curves)

        return equity_df

    def get_returns_distribution(self) -> pd.DataFrame:
        """Get daily returns for all strategies.

        Returns:
            DataFrame with date index and columns for each strategy's daily returns
        """
        if not self.results:
            raise ValueError("Must run compare() first")

        returns = {}

        for name, result in self.results.items():
            if result and result.daily_returns is not None:
                returns[name] = result.daily_returns

        if not returns:
            return pd.DataFrame()

        # Combine into single DataFrame
        returns_df = pd.DataFrame(returns)

        return returns_df

    def export_to_csv(self, filename: str):
        """Export comparison results to CSV.

        Args:
            filename: Output CSV file path
        """
        if self.comparison_df is None:
            raise ValueError("Must run compare() first")

        self.comparison_df.to_csv(filename, index=False)
        logger.info("Comparison results exported to %s", filename)

    def get_correlation_matrix(self) -> pd.DataFrame:
        """Get correlation matrix of strategy returns.

        Returns:
            DataFrame with correlation coefficients between strategies
        """
        returns_df = self.get_returns_distribution()

        if returns_df.empty:
            return pd.DataFrame()

        return returns_df.corr()
