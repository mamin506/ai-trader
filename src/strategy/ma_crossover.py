"""Moving Average Crossover Strategy.

This module implements a dual moving average crossover strategy, which is a classic
trend-following approach. It generates buy signals when a fast MA crosses above a slow MA,
and sell signals when the fast MA crosses below the slow MA.

This is the Phase 1 reference strategy for the AI Trader system.
"""

import pandas as pd

from src.strategy.base import Strategy
from src.strategy.indicators import sma
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MACrossoverStrategy(Strategy):
    """Dual Moving Average Crossover Strategy.

    Generates trading signals based on the crossover of two simple moving averages:
    - Fast MA (shorter period): More reactive to recent price changes
    - Slow MA (longer period): Smoother, follows longer-term trend

    Signal Logic:
        - Buy (+1.0): Fast MA crosses above Slow MA (golden cross)
        - Sell (-1.0): Fast MA crosses below Slow MA (death cross)
        - Hold (0.0): No crossover

    Parameters:
        - fast_period (int): Period for fast moving average (default: 20)
        - slow_period (int): Period for slow moving average (default: 50)
        - min_required_rows (int): Minimum data points needed (default: 100)

    Example:
        >>> from src.api.data_api import DataAPI
        >>> from src.strategy.ma_crossover import MACrossoverStrategy
        >>>
        >>> # Initialize strategy
        >>> strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
        >>>
        >>> # Fetch data
        >>> api = DataAPI()
        >>> data = api.get_daily_bars('AAPL', '2024-01-01', '2024-12-31')
        >>>
        >>> # Generate signals
        >>> signals = strategy.generate_signals(data)
        >>> buy_dates = signals[signals == 1.0].index
        >>> sell_dates = signals[signals == -1.0].index
    """

    def validate_params(self) -> None:
        """Validate required parameters.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Check required parameters exist
        if "fast_period" not in self.params:
            raise ValueError("'fast_period' parameter required")
        if "slow_period" not in self.params:
            raise ValueError("'slow_period' parameter required")

        # Validate parameter values
        if self.params["fast_period"] < 1:
            raise ValueError("'fast_period' must be positive")
        if self.params["slow_period"] < 1:
            raise ValueError("'slow_period' must be positive")

        # Ensure fast < slow (conceptually, fast should respond quicker)
        if self.params["fast_period"] >= self.params["slow_period"]:
            raise ValueError("'fast_period' must be less than 'slow_period'")

        logger.debug(
            "MA Crossover params validated: fast=%d, slow=%d",
            self.params["fast_period"],
            self.params["slow_period"],
        )

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate fast and slow moving averages.

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with original data plus 'fast_ma' and 'slow_ma' columns
        """
        data = data.copy()

        # Calculate moving averages
        data["fast_ma"] = sma(data["close"], period=self.params["fast_period"])
        data["slow_ma"] = sma(data["close"], period=self.params["slow_period"])

        logger.debug(
            "Calculated MAs: fast_ma (period=%d), slow_ma (period=%d)",
            self.params["fast_period"],
            self.params["slow_period"],
        )

        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on MA crossover.

        Signal Generation Rules:
        1. Golden Cross (Buy): Fast MA crosses ABOVE Slow MA
           - Current: fast_ma > slow_ma
           - Previous: fast_ma <= slow_ma
           - Signal: +1.0

        2. Death Cross (Sell): Fast MA crosses BELOW Slow MA
           - Current: fast_ma < slow_ma
           - Previous: fast_ma >= slow_ma
           - Signal: -1.0

        3. No Crossover (Hold): No change in relationship
           - Signal: 0.0

        Args:
            data: OHLCV DataFrame

        Returns:
            Series with signal values in [-1.0, 1.0]
        """
        # Calculate indicators
        data = self.calculate_indicators(data)

        # Initialize all signals to 0 (hold)
        signals = pd.Series(0.0, index=data.index, name="signal")

        # Detect crossovers by comparing current and previous MA relationships
        # Fill NaN with False to avoid issues with boolean operations
        fast_above_slow = (data["fast_ma"] > data["slow_ma"]).fillna(False)
        fast_above_slow_prev = fast_above_slow.shift(1).fillna(False)

        # Golden Cross: Fast MA crosses above Slow MA (bullish signal)
        golden_cross = fast_above_slow & (~fast_above_slow_prev)
        signals[golden_cross] = 1.0

        # Death Cross: Fast MA crosses below Slow MA (bearish signal)
        death_cross = (~fast_above_slow) & fast_above_slow_prev
        signals[death_cross] = -1.0

        # Log signal summary
        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()
        hold_signals = (signals == 0.0).sum()

        logger.info(
            "Generated signals - Buy: %d, Sell: %d, Hold: %d",
            buy_signals,
            sell_signals,
            hold_signals,
        )

        return signals
