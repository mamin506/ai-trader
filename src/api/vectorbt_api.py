"""VectorBT API - High-level interface for fast backtesting and optimization.

This module provides a simple API for:
1. Fast vectorized backtesting (100-1000x faster than event-driven)
2. Parameter optimization across many combinations
3. Strategy screening across multiple symbols

Example:
    >>> from src.api.vectorbt_api import VectorBTAPI
    >>> from src.strategy.ma_crossover import MACrossoverStrategy
    >>>
    >>> api = VectorBTAPI()
    >>>
    >>> # 1. Fast backtest
    >>> result = api.quick_backtest(
    ...     strategy=strategy,
    ...     symbol='AAPL',
    ...     start_date='2023-01-01',
    ...     end_date='2024-01-01'
    ... )
    >>> print(f"Return: {result.total_return:.2%}, Sharpe: {result.sharpe_ratio:.2f}")
    >>>
    >>> # 2. Parameter optimization
    >>> best_params = api.optimize_strategy(
    ...     strategy_class=MACrossoverStrategy,
    ...     symbol='AAPL',
    ...     param_grid={'fast_period': [10, 20, 30], 'slow_period': [50, 100, 200]},
    ...     start_date='2023-01-01',
    ...     end_date='2024-01-01'
    ... )
"""

from datetime import datetime
from typing import Dict, List, Optional, Type, Union

import pandas as pd

from src.api.data_api import DataAPI
from src.execution.vectorbt_backtest import VectorBTBacktest, VectorBTResult
from src.strategy.base import Strategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VectorBTAPI:
    """High-level API for VectorBT-based fast backtesting.

    Provides simple methods for quick backtesting and parameter optimization.

    Example:
        >>> api = VectorBTAPI()
        >>>
        >>> # Quick backtest
        >>> result = api.quick_backtest(strategy, 'AAPL', '2023-01-01', '2024-01-01')
        >>>
        >>> # Optimize parameters
        >>> results = api.optimize_strategy(
        ...     MACrossoverStrategy,
        ...     'AAPL',
        ...     {'fast_period': [10, 20, 30], 'slow_period': [50, 100]},
        ...     '2023-01-01',
        ...     '2024-01-01'
        ... )
    """

    def __init__(
        self,
        data_api: Optional[DataAPI] = None,
        initial_cash: float = 100000.0,
        commission: float = 0.001,
        slippage_pct: float = 0.001,
    ):
        """Initialize VectorBT API.

        Args:
            data_api: DataAPI instance (creates new if None)
            initial_cash: Starting capital
            commission: Commission as decimal
            slippage_pct: Slippage as decimal
        """
        self.data_api = data_api or DataAPI()
        self.backtest = VectorBTBacktest(
            initial_cash=initial_cash,
            commission=commission,
            slippage_pct=slippage_pct,
        )

        logger.debug("VectorBTAPI initialized")

    def quick_backtest(
        self,
        strategy: Strategy,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
    ) -> VectorBTResult:
        """Run quick vectorized backtest for a strategy.

        Fast alternative to BacktestAPI for initial strategy validation.

        Args:
            strategy: Strategy instance with configured parameters
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date ('YYYY-MM-DD' or datetime)
            end_date: End date ('YYYY-MM-DD' or datetime)

        Returns:
            VectorBTResult with performance metrics

        Example:
            >>> from src.strategy.ma_crossover import MACrossoverStrategy
            >>>
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> result = api.quick_backtest(strategy, 'AAPL', '2023-01-01', '2024-01-01')
            >>> print(f"Sharpe: {result.sharpe_ratio:.2f}")
        """
        logger.info(
            "Running quick backtest: %s %s from %s to %s",
            strategy.__class__.__name__,
            symbol,
            start_date,
            end_date,
        )

        # Fetch data
        price_data = self.data_api.get_daily_bars(symbol, start_date, end_date)

        # Generate signals
        signals = strategy.generate_signals(price_data)

        # Run VectorBT backtest
        result = self.backtest.run_from_signals(price_data, signals)

        logger.info(
            "Quick backtest complete: %.2f%% return, %.2f Sharpe",
            result.total_return * 100,
            result.sharpe_ratio,
        )

        return result

    def optimize_strategy(
        self,
        strategy_class: Type[Strategy],
        symbol: str,
        param_grid: Dict[str, List],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> pd.DataFrame:
        """Optimize strategy parameters using grid search.

        Tests all parameter combinations and returns best results.

        Args:
            strategy_class: Strategy class (not instance)
            symbol: Stock symbol
            param_grid: Dict mapping parameter names to value lists
            start_date: Start date
            end_date: End date
            metric: Metric to optimize ('sharpe_ratio', 'total_return', etc.)
            top_n: Number of top results to return

        Returns:
            DataFrame with top N parameter combinations sorted by metric

        Example:
            >>> results = api.optimize_strategy(
            ...     MACrossoverStrategy,
            ...     'AAPL',
            ...     {'fast_period': [10, 20, 30], 'slow_period': [50, 100, 200]},
            ...     '2023-01-01',
            ...     '2024-01-01',
            ...     metric='sharpe_ratio',
            ...     top_n=5
            ... )
            >>> print(f"Best params: {results.iloc[0]}")
        """
        logger.info(
            "Optimizing %s on %s: %d combinations",
            strategy_class.__name__,
            symbol,
            self._count_combinations(param_grid),
        )

        # Fetch data
        price_data = self.data_api.get_daily_bars(symbol, start_date, end_date)

        # Define signal generator
        def generate_signals(params):
            strategy = strategy_class(params)
            return strategy.generate_signals(price_data)

        # Run optimization
        results = self.backtest.optimize_parameters(
            price_data=price_data,
            param_grid=param_grid,
            signal_generator=generate_signals,
            metric=metric,
        )

        # Return top N
        top_results = results.head(top_n)

        logger.info(
            "Optimization complete: Best %s = %.4f (params: %s)",
            metric,
            top_results.iloc[0][metric],
            self._format_params(top_results.iloc[0], param_grid.keys()),
        )

        return top_results

    def batch_backtest(
        self,
        strategy: Strategy,
        symbols: List[str],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
    ) -> pd.DataFrame:
        """Run backtest across multiple symbols.

        Useful for strategy screening and portfolio construction.

        Args:
            strategy: Strategy instance
            symbols: List of symbols to test
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with results for each symbol

        Example:
            >>> symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META']
            >>> results = api.batch_backtest(strategy, symbols, '2023-01-01', '2024-01-01')
            >>> results = results.sort_values('sharpe_ratio', ascending=False)
            >>> print(f"Best performer: {results.iloc[0]['symbol']}")
        """
        logger.info(
            "Running batch backtest: %s strategy on %d symbols",
            strategy.__class__.__name__,
            len(symbols),
        )

        results = []
        for symbol in symbols:
            try:
                result = self.quick_backtest(strategy, symbol, start_date, end_date)
                results.append(
                    {
                        "symbol": symbol,
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
                logger.warning("Backtest failed for %s: %s", symbol, e)
                continue

        results_df = pd.DataFrame(results)

        logger.info(
            "Batch backtest complete: %d/%d symbols successful",
            len(results_df),
            len(symbols),
        )

        return results_df

    def _count_combinations(self, param_grid: Dict[str, List]) -> int:
        """Count total parameter combinations."""
        count = 1
        for values in param_grid.values():
            count *= len(values)
        return count

    def _format_params(self, row: pd.Series, param_names) -> str:
        """Format parameter values for display."""
        params = {name: row[name] for name in param_names if name in row.index}
        return str(params)
