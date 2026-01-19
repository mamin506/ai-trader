"""User-friendly Strategy API for testing trading strategies.

This module provides a simple, high-level interface for applying strategies
to historical market data and evaluating their performance.
"""

from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from src.api.data_api import DataAPI
from src.data.base import DataProvider
from src.strategy.base import Strategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StrategyAPI:
    """High-level API for testing trading strategies.

    Provides simple methods for generating signals and evaluating strategy
    performance on historical data.

    Example:
        >>> from src.api.strategy_api import StrategyAPI
        >>> from src.strategy.ma_crossover import MACrossoverStrategy
        >>>
        >>> # Initialize API and strategy
        >>> api = StrategyAPI()
        >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
        >>>
        >>> # Get signals for AAPL in 2024
        >>> signals = api.get_signals('AAPL', strategy, '2024-01-01', '2024-12-31')
        >>> print(f"Buy signals: {(signals == 1.0).sum()}")
        >>> print(f"Sell signals: {(signals == -1.0).sum()}")
        >>>
        >>> # Run simple backtest
        >>> results = api.backtest('AAPL', strategy, '2024-01-01', '2024-12-31')
        >>> print(f"Total return: {results['total_return']:.2%}")
    """

    def __init__(self, data_api: Optional[DataAPI] = None):
        """Initialize StrategyAPI.

        Args:
            data_api: DataAPI instance (defaults to new instance)
        """
        self.data_api = data_api or DataAPI()
        logger.debug("StrategyAPI initialized with %s", type(self.data_api).__name__)

    def get_signals(
        self,
        symbol: str,
        strategy: Strategy,
        start: str | datetime,
        end: str | datetime,
    ) -> pd.Series:
        """Generate trading signals for a symbol using a strategy.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            strategy: Strategy instance to apply
            start: Start date (ISO format string or datetime)
            end: End date (ISO format string or datetime)

        Returns:
            Series with signal values in [-1.0, 1.0]
            Index: DatetimeIndex with dates
            Values: -1.0 (sell), 0.0 (hold), 1.0 (buy)

        Example:
            >>> api = StrategyAPI()
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> signals = api.get_signals('AAPL', strategy, '2024-01-01', '2024-12-31')
            >>> buy_dates = signals[signals == 1.0].index
        """
        logger.info("Generating signals for %s from %s to %s", symbol, start, end)

        # Fetch historical data
        data = self.data_api.get_daily_bars(symbol, start, end)

        if data.empty:
            logger.warning("No data available for %s", symbol)
            return pd.Series(dtype=float, name="signal")

        # Validate data quality
        if not strategy.validate_data(data):
            logger.warning("Data validation failed for %s", symbol)
            return pd.Series(dtype=float, name="signal")

        # Generate signals
        signals = strategy.generate_signals(data)

        logger.info(
            "Generated %d signals for %s: %d buy, %d sell, %d hold",
            len(signals),
            symbol,
            (signals == 1.0).sum(),
            (signals == -1.0).sum(),
            (signals == 0.0).sum(),
        )

        return signals

    def backtest(
        self,
        symbol: str,
        strategy: Strategy,
        start: str | datetime,
        end: str | datetime,
        initial_capital: float = 10000.0,
    ) -> Dict:
        """Run simple backtest of strategy on historical data.

        This is a basic evaluation that assumes:
        - Buy/sell entire position on each signal
        - No transaction costs
        - Perfect execution at close prices

        For production backtesting, use VectorBT or similar framework.

        Args:
            symbol: Ticker symbol
            strategy: Strategy instance to test
            start: Start date
            end: End date
            initial_capital: Starting capital in dollars (default: $10,000)

        Returns:
            Dictionary with backtest results:
                - total_return: Percentage return
                - num_trades: Number of round-trip trades
                - num_signals: Total signals generated
                - final_value: Portfolio value at end
                - buy_and_hold_return: Comparison benchmark

        Example:
            >>> api = StrategyAPI()
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> results = api.backtest('AAPL', strategy, '2024-01-01', '2024-12-31')
            >>> print(f"Strategy return: {results['total_return']:.2%}")
            >>> print(f"Buy & hold return: {results['buy_and_hold_return']:.2%}")
        """
        logger.info("Running backtest for %s from %s to %s", symbol, start, end)

        # Fetch data and generate signals
        data = self.data_api.get_daily_bars(symbol, start, end)
        if data.empty:
            logger.error("No data available for backtest")
            return {
                "total_return": 0.0,
                "num_trades": 0,
                "num_signals": 0,
                "final_value": initial_capital,
                "buy_and_hold_return": 0.0,
            }

        signals = strategy.generate_signals(data)

        # Merge signals with price data
        backtest_data = data.copy()
        backtest_data["signal"] = signals

        # Simple backtest logic: follow signals exactly
        # Start with all cash
        cash = initial_capital
        shares = 0.0
        position = 0  # 0 = no position, 1 = long

        trades = []

        for date, row in backtest_data.iterrows():
            signal = row["signal"]
            price = row["close"]

            # Buy signal and we're not in a position
            if signal == 1.0 and position == 0:
                shares = cash / price
                cash = 0.0
                position = 1
                trades.append({"date": date, "action": "buy", "price": price})
                logger.debug("BUY at %s: %.2f (shares: %.2f)", date, price, shares)

            # Sell signal and we're in a position
            elif signal == -1.0 and position == 1:
                cash = shares * price
                shares = 0.0
                position = 0
                trades.append({"date": date, "action": "sell", "price": price})
                logger.debug("SELL at %s: %.2f (cash: %.2f)", date, price, cash)

        # Close any open position at the end
        if position == 1:
            final_price = backtest_data.iloc[-1]["close"]
            cash = shares * final_price
            shares = 0.0
            logger.debug("Closing position at end: %.2f", final_price)

        final_value = cash + (shares * backtest_data.iloc[-1]["close"])
        total_return = (final_value - initial_capital) / initial_capital

        # Calculate buy-and-hold benchmark
        buy_hold_shares = initial_capital / backtest_data.iloc[0]["close"]
        buy_hold_final = buy_hold_shares * backtest_data.iloc[-1]["close"]
        buy_hold_return = (buy_hold_final - initial_capital) / initial_capital

        num_buy_signals = (signals == 1.0).sum()
        num_sell_signals = (signals == -1.0).sum()
        num_round_trips = min(num_buy_signals, num_sell_signals)

        results = {
            "total_return": total_return,
            "num_trades": len(trades),
            "num_signals": num_buy_signals + num_sell_signals,
            "final_value": final_value,
            "buy_and_hold_return": buy_hold_return,
            "num_buy_signals": num_buy_signals,
            "num_sell_signals": num_sell_signals,
            "num_round_trips": num_round_trips,
            "initial_capital": initial_capital,
        }

        logger.info(
            "Backtest complete: return=%.2f%%, trades=%d, final_value=$%.2f",
            total_return * 100,
            len(trades),
            final_value,
        )

        return results

    def get_strategy_data(
        self,
        symbol: str,
        strategy: Strategy,
        start: str | datetime,
        end: str | datetime,
    ) -> pd.DataFrame:
        """Get historical data with indicators calculated by strategy.

        Useful for debugging and visualizing strategy logic.

        Args:
            symbol: Ticker symbol
            strategy: Strategy instance
            start: Start date
            end: End date

        Returns:
            DataFrame with OHLCV data plus calculated indicators

        Example:
            >>> api = StrategyAPI()
            >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
            >>> data = api.get_strategy_data('AAPL', strategy, '2024-01-01', '2024-12-31')
            >>> print(data[['close', 'fast_ma', 'slow_ma']].tail())
        """
        logger.info("Fetching strategy data for %s", symbol)

        # Fetch historical data
        data = self.data_api.get_daily_bars(symbol, start, end)

        if data.empty:
            logger.warning("No data available for %s", symbol)
            return pd.DataFrame()

        # Calculate indicators
        data_with_indicators = strategy.calculate_indicators(data)

        # Add signals
        signals = strategy.generate_signals(data)
        data_with_indicators["signal"] = signals

        logger.info(
            "Retrieved strategy data for %s: %d rows with indicators",
            symbol,
            len(data_with_indicators),
        )

        return data_with_indicators
