"""Grid search parameter optimization for trading strategies.

This module provides a GridSearchOptimizer that exhaustively searches through
parameter combinations to find the optimal configuration for a trading strategy.
"""

from typing import Dict, List, Any, Tuple
from itertools import product
import pandas as pd

from src.api.backtest_api import BacktestAPI
from src.strategy.base import Strategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class GridSearchOptimizer:
    """Grid search optimizer for strategy parameters.

    Performs exhaustive search over parameter grid to find the combination
    that maximizes a specified metric (e.g., Sharpe ratio, total return).

    Example:
        >>> from src.strategy.ma_crossover import MACDStrategy
        >>> from src.optimization import GridSearchOptimizer
        >>>
        >>> # Define parameter grid
        >>> param_grid = {
        ...     'fast_period': [10, 20, 30],
        ...     'slow_period': [50, 100, 200],
        ... }
        >>>
        >>> # Optimize
        >>> optimizer = GridSearchOptimizer(MACDStrategy, param_grid)
        >>> best_params, results = optimizer.optimize(
        ...     symbols=['AAPL', 'MSFT'],
        ...     start_date='2023-01-01',
        ...     end_date='2024-01-01',
        ...     metric='sharpe_ratio'
        ... )
    """

    def __init__(
        self,
        strategy_class: type[Strategy],
        param_grid: Dict[str, List[Any]],
        fixed_params: Dict[str, Any] = None,
    ):
        """Initialize grid search optimizer.

        Args:
            strategy_class: Strategy class to optimize (e.g., MACrossoverStrategy)
            param_grid: Dictionary of parameter names to lists of values to try
                       Example: {'fast_period': [10, 20, 30], 'slow_period': [50, 100]}
            fixed_params: Parameters to keep constant across all tests
                         Example: {'min_required_rows': 50}
        """
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.fixed_params = fixed_params or {}
        self.backtest_api = BacktestAPI()

        # Validate param_grid
        if not param_grid:
            raise ValueError("param_grid cannot be empty")

        for param, values in param_grid.items():
            if not isinstance(values, list) or len(values) == 0:
                raise ValueError(f"Parameter '{param}' must have at least one value")

        logger.info(
            "Initialized GridSearchOptimizer for %s with %d parameters",
            strategy_class.__name__,
            len(param_grid),
        )

    def _generate_param_combinations(self) -> List[Dict[str, Any]]:
        """Generate all combinations of parameters from the grid.

        Returns:
            List of parameter dictionaries, each representing one combination
        """
        # Get parameter names and value lists
        param_names = list(self.param_grid.keys())
        param_values = [self.param_grid[name] for name in param_names]

        # Generate all combinations using itertools.product
        combinations = []
        for values in product(*param_values):
            # Create parameter dict
            params = dict(zip(param_names, values))

            # Add fixed parameters
            params.update(self.fixed_params)

            combinations.append(params)

        logger.debug("Generated %d parameter combinations", len(combinations))
        return combinations

    def optimize(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        metric: str = "sharpe_ratio",
        initial_capital: float = 100000.0,
        rebalance_frequency: str = "weekly",
        verbose: bool = True,
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Run grid search optimization.

        Args:
            symbols: List of stock symbols to backtest on
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            metric: Metric to optimize ('sharpe_ratio', 'total_return', 'max_drawdown')
            initial_capital: Starting capital for backtest
            rebalance_frequency: 'daily', 'weekly', or 'monthly'
            verbose: Whether to print progress

        Returns:
            Tuple of (best_params, results_df) where:
                - best_params: Dictionary of optimal parameter values
                - results_df: DataFrame with all tested combinations and their metrics
        """
        if metric not in ["sharpe_ratio", "total_return", "max_drawdown"]:
            raise ValueError(
                f"Invalid metric '{metric}'. Must be one of: "
                "sharpe_ratio, total_return, max_drawdown"
            )

        logger.info(
            "Starting grid search optimization on %d symbols from %s to %s",
            len(symbols),
            start_date,
            end_date,
        )

        # Generate all parameter combinations
        param_combinations = self._generate_param_combinations()

        if verbose:
            print(f"\n🔍 Grid Search Optimization")
            print(f"Strategy: {self.strategy_class.__name__}")
            print(f"Symbols: {', '.join(symbols)}")
            print(f"Period: {start_date} to {end_date}")
            print(f"Combinations to test: {len(param_combinations)}")
            print(f"Optimizing for: {metric}\n")

        # Test each combination
        results = []
        for i, params in enumerate(param_combinations, 1):
            if verbose and i % max(1, len(param_combinations) // 10) == 0:
                print(f"Progress: {i}/{len(param_combinations)} ({100*i//len(param_combinations)}%)")

            try:
                # Create strategy with current parameters
                strategy = self.strategy_class(params)

                # Run backtest
                result = self.backtest_api.run_backtest(
                    strategy=strategy,
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    rebalance_frequency=rebalance_frequency,
                )

                # Extract metrics
                results.append({
                    **params,  # Include all parameters
                    "total_return": result.total_return,
                    "annualized_return": result.annualized_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "num_trades": result.num_trades,
                    "win_rate": result.win_rate,
                })

                logger.debug(
                    "Tested params %s: %s=%.4f",
                    params,
                    metric,
                    results[-1][metric],
                )

            except Exception as e:
                logger.warning(
                    "Failed to backtest params %s: %s",
                    params,
                    str(e),
                )
                # Add failed result with NaN metrics
                results.append({
                    **params,
                    "total_return": float('nan'),
                    "annualized_return": float('nan'),
                    "sharpe_ratio": float('nan'),
                    "max_drawdown": float('nan'),
                    "num_trades": 0,
                    "win_rate": 0.0,
                })

        # Convert to DataFrame
        results_df = pd.DataFrame(results)

        # Find best parameters based on metric
        if metric == "max_drawdown":
            # For drawdown, lower (more negative) is worse, so find minimum absolute value
            best_idx = results_df["max_drawdown"].abs().idxmin()
        else:
            # For return and Sharpe, higher is better
            best_idx = results_df[metric].idxmax()

        best_params = results_df.loc[best_idx, list(self.param_grid.keys())].to_dict()

        # Sort results by metric
        if metric == "max_drawdown":
            results_df = results_df.sort_values(metric, ascending=True)
        else:
            results_df = results_df.sort_values(metric, ascending=False)

        if verbose:
            print(f"\n✅ Optimization Complete!")
            print(f"\nBest Parameters ({metric}={results_df.iloc[0][metric]:.4f}):")
            for param, value in best_params.items():
                print(f"  {param}: {value}")
            print(f"\nTop 5 Combinations:")
            print(results_df.head().to_string(index=False))

        logger.info(
            "Grid search complete. Best %s: %.4f with params: %s",
            metric,
            results_df.iloc[0][metric],
            best_params,
        )

        return best_params, results_df

    def get_param_combinations_count(self) -> int:
        """Get the total number of parameter combinations that will be tested.

        Returns:
            Number of combinations
        """
        count = 1
        for values in self.param_grid.values():
            count *= len(values)
        return count
