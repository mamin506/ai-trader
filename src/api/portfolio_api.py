"""User-friendly Portfolio API for portfolio management and analysis.

This module provides a simple, high-level interface for portfolio allocation,
rebalancing, and performance tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.api.data_api import DataAPI
from src.api.strategy_api import StrategyAPI
from src.portfolio.base import AllocationResult, Order, PortfolioManager, PortfolioState
from src.portfolio.heuristic_allocator import HeuristicAllocator
from src.strategy.base import Strategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PortfolioAPI:
    """High-level API for portfolio management.

    Provides simple methods for portfolio allocation, rebalancing decisions,
    and performance analysis.

    Example:
        >>> from src.api.portfolio_api import PortfolioAPI
        >>> from src.strategy.ma_crossover import MACrossoverStrategy
        >>>
        >>> # Initialize API
        >>> api = PortfolioAPI()
        >>>
        >>> # Define universe and strategy
        >>> symbols = ['AAPL', 'MSFT', 'GOOGL']
        >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
        >>>
        >>> # Get allocation recommendation
        >>> result = api.get_allocation(
        ...     symbols=symbols,
        ...     strategy=strategy,
        ...     portfolio_value=100000.0,
        ...     as_of_date='2024-12-31'
        ... )
        >>> print(result['target_weights'])
    """

    def __init__(
        self,
        allocator: Optional[PortfolioManager] = None,
        strategy_api: Optional[StrategyAPI] = None,
        data_api: Optional[DataAPI] = None,
    ):
        """Initialize PortfolioAPI.

        Args:
            allocator: PortfolioManager instance (defaults to HeuristicAllocator)
            strategy_api: StrategyAPI instance (defaults to new instance)
            data_api: DataAPI instance (defaults to new instance)
        """
        self.allocator = allocator or HeuristicAllocator()
        self.data_api = data_api or DataAPI()
        self.strategy_api = strategy_api or StrategyAPI(data_api=self.data_api)

        logger.debug(
            "PortfolioAPI initialized with %s", type(self.allocator).__name__
        )

    def get_allocation(
        self,
        symbols: List[str],
        strategy: Strategy,
        portfolio_value: float,
        as_of_date: str | datetime,
        current_positions: Optional[Dict[str, float]] = None,
        lookback_days: int = 252,
    ) -> Dict:
        """Get portfolio allocation based on strategy signals.

        Generates signals for all symbols using the provided strategy,
        then calculates target portfolio weights and rebalancing orders.

        Args:
            symbols: List of ticker symbols in the universe
            strategy: Strategy instance to generate signals
            portfolio_value: Total portfolio value in dollars
            as_of_date: Date for which to calculate allocation
            current_positions: Current holdings {symbol: dollar_value} (default: all cash)
            lookback_days: Days of history to fetch for signal generation (default: 252)

        Returns:
            Dictionary with:
                - signals: Dict of {symbol: signal_value}
                - target_weights: Dict of {symbol: weight}
                - orders: List of Order objects
                - metrics: Allocation metrics

        Example:
            >>> api = PortfolioAPI()
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> result = api.get_allocation(
            ...     symbols=['AAPL', 'MSFT', 'GOOGL'],
            ...     strategy=strategy,
            ...     portfolio_value=100000.0,
            ...     as_of_date='2024-12-31'
            ... )
        """
        logger.info(
            "Calculating allocation for %d symbols as of %s", len(symbols), as_of_date
        )

        # Parse date
        if isinstance(as_of_date, str):
            end_date = datetime.fromisoformat(as_of_date)
        else:
            end_date = as_of_date

        # Calculate start date for lookback
        from datetime import timedelta

        start_date = end_date - timedelta(days=lookback_days)

        # Generate signals for all symbols
        signals = {}
        prices = {}

        for symbol in symbols:
            try:
                # Get signals using StrategyAPI
                signal_series = self.strategy_api.get_signals(
                    symbol=symbol,
                    strategy=strategy,
                    start=start_date,
                    end=end_date,
                )

                if not signal_series.empty:
                    # Use the latest signal
                    signals[symbol] = float(signal_series.iloc[-1])

                    # Get latest price
                    data = self.data_api.get_daily_bars(symbol, start_date, end_date)
                    if not data.empty:
                        prices[symbol] = float(data.iloc[-1]["close"])

            except Exception as e:
                logger.warning("Failed to get signal for %s: %s", symbol, e)
                continue

        if not signals:
            logger.warning("No valid signals generated for any symbol")
            return {
                "signals": {},
                "target_weights": {"Cash": 1.0},
                "orders": [],
                "metrics": {},
            }

        logger.info("Generated signals: %s", signals)

        # Create portfolio state
        if current_positions is None:
            current_positions = {}

        cash = portfolio_value - sum(current_positions.values())
        portfolio = PortfolioState(
            positions=current_positions,
            total_value=portfolio_value,
            cash=max(0.0, cash),
            prices=prices,
        )

        # Calculate allocation
        result = self.allocator.allocate(signals=signals, portfolio=portfolio)

        return {
            "signals": signals,
            "target_weights": result.target_weights,
            "orders": result.orders,
            "metrics": result.metrics,
        }

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        threshold: float = 0.05,
    ) -> bool:
        """Check if portfolio should be rebalanced.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            threshold: Maximum allowed drift (default: 5%)

        Returns:
            True if any position drifted more than threshold

        Example:
            >>> api = PortfolioAPI()
            >>> current = {'AAPL': 0.30, 'MSFT': 0.20, 'Cash': 0.50}
            >>> target = {'AAPL': 0.25, 'MSFT': 0.25, 'Cash': 0.50}
            >>> if api.should_rebalance(current, target):
            ...     print("Rebalancing recommended")
        """
        return self.allocator.should_rebalance(current_weights, target_weights, threshold)

    def analyze_signals(
        self,
        symbols: List[str],
        strategy: Strategy,
        start: str | datetime,
        end: str | datetime,
    ) -> pd.DataFrame:
        """Analyze signals across multiple symbols.

        Generates signals for all symbols and returns a DataFrame
        for easy comparison and analysis.

        Args:
            symbols: List of ticker symbols
            strategy: Strategy instance
            start: Start date
            end: End date

        Returns:
            DataFrame with columns for each symbol's signals,
            indexed by date

        Example:
            >>> api = PortfolioAPI()
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> signals_df = api.analyze_signals(
            ...     symbols=['AAPL', 'MSFT', 'GOOGL'],
            ...     strategy=strategy,
            ...     start='2024-01-01',
            ...     end='2024-12-31'
            ... )
            >>> # See latest signals
            >>> print(signals_df.tail())
        """
        logger.info("Analyzing signals for %d symbols from %s to %s", len(symbols), start, end)

        all_signals = {}

        for symbol in symbols:
            try:
                signals = self.strategy_api.get_signals(
                    symbol=symbol, strategy=strategy, start=start, end=end
                )
                if not signals.empty:
                    all_signals[symbol] = signals
            except Exception as e:
                logger.warning("Failed to get signals for %s: %s", symbol, e)

        if not all_signals:
            return pd.DataFrame()

        # Combine into single DataFrame
        df = pd.DataFrame(all_signals)
        df.index.name = "date"

        logger.info("Signal analysis complete: %d symbols, %d dates", len(df.columns), len(df))

        return df

    def get_latest_signals(
        self,
        symbols: List[str],
        strategy: Strategy,
        as_of_date: str | datetime,
        lookback_days: int = 252,
    ) -> Dict[str, float]:
        """Get latest signals for multiple symbols.

        Convenience method to get just the most recent signal for each symbol.

        Args:
            symbols: List of ticker symbols
            strategy: Strategy instance
            as_of_date: Reference date
            lookback_days: Days of history for signal generation

        Returns:
            Dict of {symbol: signal_value}

        Example:
            >>> api = PortfolioAPI()
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> signals = api.get_latest_signals(
            ...     symbols=['AAPL', 'MSFT'],
            ...     strategy=strategy,
            ...     as_of_date='2024-12-31'
            ... )
        """
        if isinstance(as_of_date, str):
            end_date = datetime.fromisoformat(as_of_date)
        else:
            end_date = as_of_date

        from datetime import timedelta

        start_date = end_date - timedelta(days=lookback_days)

        signals = {}
        for symbol in symbols:
            try:
                signal_series = self.strategy_api.get_signals(
                    symbol=symbol, strategy=strategy, start=start_date, end=end_date
                )
                if not signal_series.empty:
                    signals[symbol] = float(signal_series.iloc[-1])
            except Exception as e:
                logger.warning("Failed to get signal for %s: %s", symbol, e)

        return signals

    def format_orders(self, orders: List[Order]) -> pd.DataFrame:
        """Format orders as a DataFrame for display.

        Args:
            orders: List of Order objects

        Returns:
            DataFrame with order details

        Example:
            >>> result = api.get_allocation(...)
            >>> orders_df = api.format_orders(result['orders'])
            >>> print(orders_df)
        """
        if not orders:
            return pd.DataFrame(columns=["action", "symbol", "shares", "estimated_value", "reason"])

        data = [
            {
                "action": o.action.value,
                "symbol": o.symbol,
                "shares": o.shares,
                "estimated_value": o.estimated_value,
                "reason": o.reason,
            }
            for o in orders
        ]

        return pd.DataFrame(data)

    def format_weights(self, weights: Dict[str, float]) -> pd.DataFrame:
        """Format weights as a DataFrame for display.

        Args:
            weights: Dict of {symbol: weight}

        Returns:
            DataFrame with weight details, sorted by weight descending

        Example:
            >>> result = api.get_allocation(...)
            >>> weights_df = api.format_weights(result['target_weights'])
            >>> print(weights_df)
        """
        data = [{"symbol": s, "weight": w, "weight_pct": f"{w:.1%}"} for s, w in weights.items()]

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("weight", ascending=False).reset_index(drop=True)

        return df
