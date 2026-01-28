"""VectorBT-based high-performance backtesting.

This module provides vectorized backtesting using VectorBT for fast
parameter optimization and batch backtesting. It complements the detailed
event-driven BacktestExecutor with 100-1000x faster execution.

Use Cases:
    - Parameter optimization (testing 100+ combinations)
    - Strategy screening across many symbols
    - Walk-forward analysis
    - Quick performance validation

Example:
    >>> import pandas as pd
    >>> from src.execution.vectorbt_backtest import VectorBTBacktest
    >>>
    >>> # Create backtest instance
    >>> vbt_backtest = VectorBTBacktest(
    ...     initial_cash=100000,
    ...     commission=0.001
    ... )
    >>>
    >>> # Run backtest from signals
    >>> result = vbt_backtest.run_from_signals(
    ...     price_data=price_df,
    ...     signals=signal_series
    ... )
    >>>
    >>> print(f"Total Return: {result['total_return']:.2%}")
    >>> print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
import vectorbt as vbt

from src.utils.exceptions import AITraderError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VectorBTError(AITraderError):
    """Base exception for VectorBT-related errors."""

    pass


@dataclass
class VectorBTResult:
    """Results from a VectorBT backtest.

    Attributes:
        total_return: Total return (decimal, e.g., 0.15 = 15%)
        annualized_return: Annualized return
        sharpe_ratio: Sharpe ratio
        sortino_ratio: Sortino ratio
        max_drawdown: Maximum drawdown (decimal)
        calmar_ratio: Calmar ratio (return / max drawdown)
        win_rate: Percentage of winning trades
        num_trades: Total number of trades
        avg_trade_return: Average return per trade
        profit_factor: Ratio of gross profits to gross losses
        equity_curve: Portfolio value over time
        portfolio: VectorBT Portfolio object for advanced analysis
    """

    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    num_trades: int
    avg_trade_return: float
    profit_factor: float
    equity_curve: pd.Series
    portfolio: vbt.Portfolio


class VectorBTBacktest:
    """High-performance vectorized backtesting using VectorBT.

    Provides fast backtesting for parameter optimization and strategy screening.
    Complements BacktestExecutor with 100-1000x faster execution.

    Configuration:
        initial_cash: Starting capital (default: $100,000)
        commission: Commission as decimal (default: 0.1%)
        slippage_pct: Slippage as decimal (default: 0.1%)
        freq: Trading frequency ('D' for daily, default)

    Example:
        >>> vbt_backtest = VectorBTBacktest(
        ...     initial_cash=100000,
        ...     commission=0.001,
        ...     slippage_pct=0.001
        ... )
        >>>
        >>> # Run backtest
        >>> result = vbt_backtest.run_from_signals(
        ...     price_data=price_df,
        ...     signals=signal_series
        ... )
        >>>
        >>> # Access metrics
        >>> print(f"Sharpe: {result.sharpe_ratio:.2f}")
        >>> print(f"Max DD: {result.max_drawdown:.2%}")
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission: float = 0.001,
        slippage_pct: float = 0.001,
        freq: str = "D",
    ):
        """Initialize VectorBT backtester.

        Args:
            initial_cash: Starting capital
            commission: Commission as decimal (e.g., 0.001 = 0.1%)
            slippage_pct: Slippage as decimal
            freq: Trading frequency ('D'=daily, 'H'=hourly, etc.)

        Raises:
            ValueError: If parameters are invalid
        """
        if initial_cash <= 0:
            raise ValueError(f"initial_cash must be positive, got {initial_cash}")
        if commission < 0:
            raise ValueError(f"commission must be non-negative, got {commission}")
        if slippage_pct < 0:
            raise ValueError(f"slippage_pct must be non-negative, got {slippage_pct}")

        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.freq = freq

        logger.debug(
            "VectorBTBacktest initialized: cash=$%.2f, commission=%.2f%%, slippage=%.2f%%",
            initial_cash,
            commission * 100,
            slippage_pct * 100,
        )

    def run_from_signals(
        self,
        price_data: pd.DataFrame,
        signals: Union[pd.Series, Dict[str, float]],
        symbol_column: str = "close",
    ) -> VectorBTResult:
        """Run backtest from trading signals.

        Converts signals to entry/exit points and runs vectorized backtest.

        Args:
            price_data: DataFrame with price data (must have datetime index)
            signals: Series with signal values [-1.0 to 1.0] or dict
            symbol_column: Column name for price (default: 'close')

        Returns:
            VectorBTResult with performance metrics

        Raises:
            VectorBTError: If backtest fails

        Example:
            >>> # Signals as Series
            >>> signals = pd.Series([0.0, 0.5, 1.0, 0.0, -1.0], index=dates)
            >>> result = vbt_backtest.run_from_signals(price_df, signals)
            >>>
            >>> # Signals as dict (for specific dates)
            >>> signals = {'2024-01-15': 1.0, '2024-03-20': -1.0}
            >>> result = vbt_backtest.run_from_signals(price_df, signals)
        """
        try:
            # Validate inputs
            if not isinstance(price_data, pd.DataFrame):
                raise VectorBTError("price_data must be a DataFrame")

            if symbol_column not in price_data.columns:
                raise VectorBTError(
                    f"Column '{symbol_column}' not found in price_data"
                )

            # Get price series
            prices = price_data[symbol_column]

            # Convert signals to Series if dict
            if isinstance(signals, dict):
                signals = pd.Series(signals)

            # Ensure signals align with prices
            signals = signals.reindex(prices.index, fill_value=0.0)

            # Convert signals to entry/exit points
            # Signal > 0: Enter long
            # Signal < 0: Exit long
            # Signal == 0: Hold current position
            entries = signals > 0
            exits = signals < 0

            logger.debug(
                "Running VectorBT backtest: %d bars, %d entries, %d exits",
                len(prices),
                entries.sum(),
                exits.sum(),
            )

            # Create portfolio
            portfolio = vbt.Portfolio.from_signals(
                close=prices,
                entries=entries,
                exits=exits,
                init_cash=self.initial_cash,
                fees=self.commission,
                slippage=self.slippage_pct,
                freq=self.freq,
            )

            # Extract metrics
            result = self._extract_metrics(portfolio)

            logger.info(
                "VectorBT backtest complete: %.2f%% return, %.2f Sharpe, %d trades",
                result.total_return * 100,
                result.sharpe_ratio,
                result.num_trades,
            )

            return result

        except Exception as e:
            logger.error("VectorBT backtest failed: %s", e)
            raise VectorBTError(f"Backtest failed: {e}") from e

    def _extract_metrics(self, portfolio: vbt.Portfolio) -> VectorBTResult:
        """Extract performance metrics from VectorBT portfolio.

        Args:
            portfolio: VectorBT Portfolio object

        Returns:
            VectorBTResult with all metrics
        """
        # Get basic metrics
        total_return = portfolio.total_return()
        sharpe_ratio = portfolio.sharpe_ratio()
        sortino_ratio = portfolio.sortino_ratio()
        max_drawdown = portfolio.max_drawdown()
        calmar_ratio = portfolio.calmar_ratio()

        # Trade statistics
        trades = portfolio.trades.records_readable
        num_trades = len(trades) if len(trades) > 0 else 0

        # Handle case with no trades
        if num_trades == 0:
            win_rate = 0.0
            avg_trade_return = 0.0
            profit_factor = 0.0
        else:
            winning_trades = trades[trades["PnL"] > 0]
            win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0.0

            avg_trade_return = trades["Return"].mean() if "Return" in trades else 0.0

            # Profit factor: gross profits / gross losses
            gross_profits = trades[trades["PnL"] > 0]["PnL"].sum()
            gross_losses = abs(trades[trades["PnL"] < 0]["PnL"].sum())
            profit_factor = (
                gross_profits / gross_losses if gross_losses > 0 else np.inf
            )

        # Get equity curve
        equity_curve = portfolio.value()

        # Calculate annualized return
        trading_days = len(equity_curve)
        years = trading_days / 252  # Approximate trading days per year
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

        return VectorBTResult(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            num_trades=num_trades,
            avg_trade_return=avg_trade_return,
            profit_factor=profit_factor,
            equity_curve=equity_curve,
            portfolio=portfolio,
        )

    def optimize_parameters(
        self,
        price_data: pd.DataFrame,
        param_grid: Dict[str, List],
        signal_generator,
        metric: str = "sharpe_ratio",
        symbol_column: str = "close",
    ) -> pd.DataFrame:
        """Optimize strategy parameters using grid search.

        Tests all parameter combinations and returns sorted results.

        Args:
            price_data: DataFrame with price data
            param_grid: Dict mapping parameter names to value lists
            signal_generator: Callable that takes params and returns signals
            metric: Metric to optimize ('sharpe_ratio', 'total_return', etc.)
            symbol_column: Column name for price

        Returns:
            DataFrame with all results sorted by metric (descending)

        Example:
            >>> def generate_signals(params):
            ...     # Generate signals based on params
            ...     return signal_series
            >>>
            >>> results = vbt_backtest.optimize_parameters(
            ...     price_data=price_df,
            ...     param_grid={
            ...         'fast_period': [10, 20, 30],
            ...         'slow_period': [50, 100, 200]
            ...     },
            ...     signal_generator=generate_signals,
            ...     metric='sharpe_ratio'
            ... )
            >>>
            >>> print(f"Best params: {results.iloc[0]}")
        """
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        # Use itertools.product for Cartesian product
        import itertools

        param_combinations = list(itertools.product(*param_values))

        logger.info(
            "Optimizing %d parameter combinations for metric '%s'",
            len(param_combinations),
            metric,
        )

        # Run backtest for each combination
        results = []
        for params in param_combinations:
            param_dict = dict(zip(param_names, params))

            try:
                # Generate signals for this parameter set
                signals = signal_generator(param_dict)

                # Run backtest
                result = self.run_from_signals(
                    price_data, signals, symbol_column=symbol_column
                )

                # Store result
                results.append(
                    {
                        **param_dict,
                        "total_return": result.total_return,
                        "annualized_return": result.annualized_return,
                        "sharpe_ratio": result.sharpe_ratio,
                        "sortino_ratio": result.sortino_ratio,
                        "max_drawdown": result.max_drawdown,
                        "calmar_ratio": result.calmar_ratio,
                        "win_rate": result.win_rate,
                        "num_trades": result.num_trades,
                    }
                )
            except Exception as e:
                logger.warning("Backtest failed for params %s: %s", param_dict, e)
                continue

        # Convert to DataFrame and sort
        results_df = pd.DataFrame(results)

        if len(results_df) == 0:
            raise VectorBTError("All parameter combinations failed")

        # Sort by metric (descending)
        results_df = results_df.sort_values(metric, ascending=False)

        logger.info(
            "Optimization complete: Best %s = %.4f",
            metric,
            results_df.iloc[0][metric],
        )

        return results_df
