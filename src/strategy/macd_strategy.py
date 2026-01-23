"""MACD (Moving Average Convergence Divergence) Strategy.

This module implements a classic MACD crossover strategy. It generates buy signals
when the MACD line crosses above the signal line, and sell signals when it crosses below.

MACD is a trend-following momentum indicator that shows the relationship between
two moving averages of a security's price.
"""

import pandas as pd

from src.strategy.base import Strategy
from src.strategy.indicators import macd
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MACDStrategy(Strategy):
    """MACD Crossover Strategy.

    Generates trading signals based on MACD line and signal line crossovers:
    - Bullish: MACD line crosses above signal line
    - Bearish: MACD line crosses below signal line

    Signal Logic:
        - Buy (+1.0): MACD line crosses above signal line (bullish crossover)
        - Sell (-1.0): MACD line crosses below signal line (bearish crossover)
        - Hold (0.0): No crossover

    Parameters:
        - fast_period (int): Fast EMA period (default: 12)
        - slow_period (int): Slow EMA period (default: 26)
        - signal_period (int): Signal line EMA period (default: 9)
        - min_required_rows (int): Minimum data points needed (default: 100)

    Example:
        >>> from src.api.data_api import DataAPI
        >>> from src.strategy.macd_strategy import MACDStrategy
        >>>
        >>> # Initialize strategy with default MACD parameters
        >>> strategy = MACDStrategy({
        ...     'fast_period': 12,
        ...     'slow_period': 26,
        ...     'signal_period': 9
        ... })
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
        if "signal_period" not in self.params:
            raise ValueError("'signal_period' parameter required")

        # Validate parameter values
        if self.params["fast_period"] < 1:
            raise ValueError("'fast_period' must be positive")
        if self.params["slow_period"] < 1:
            raise ValueError("'slow_period' must be positive")
        if self.params["signal_period"] < 1:
            raise ValueError("'signal_period' must be positive")

        # Ensure fast < slow (standard MACD configuration)
        if self.params["fast_period"] >= self.params["slow_period"]:
            raise ValueError("'fast_period' must be less than 'slow_period'")

        logger.debug(
            "MACD params validated: fast=%d, slow=%d, signal=%d",
            self.params["fast_period"],
            self.params["slow_period"],
            self.params["signal_period"],
        )

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD indicator.

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with original data plus 'macd', 'macd_signal', 'macd_histogram' columns
        """
        data = data.copy()

        # Calculate MACD
        macd_line, signal_line, histogram = macd(
            data["close"],
            fast_period=self.params["fast_period"],
            slow_period=self.params["slow_period"],
            signal_period=self.params["signal_period"],
        )

        data["macd"] = macd_line
        data["macd_signal"] = signal_line
        data["macd_histogram"] = histogram

        logger.debug(
            "Calculated MACD: fast=%d, slow=%d, signal=%d",
            self.params["fast_period"],
            self.params["slow_period"],
            self.params["signal_period"],
        )

        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on MACD crossovers.

        Signal Generation Rules:
        1. Bullish Crossover (Buy): MACD crosses ABOVE signal line
           - Current: macd > macd_signal
           - Previous: macd <= macd_signal
           - Signal: +1.0

        2. Bearish Crossover (Sell): MACD crosses BELOW signal line
           - Current: macd < macd_signal
           - Previous: macd >= macd_signal
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

        # Detect crossovers by comparing current and previous relationships
        macd_above_signal = (data["macd"] > data["macd_signal"]).fillna(False)
        macd_above_signal_prev = macd_above_signal.shift(1, fill_value=False)

        # Bullish crossover: MACD crosses above signal line
        bullish_cross = macd_above_signal & (~macd_above_signal_prev)
        signals[bullish_cross] = 1.0

        # Bearish crossover: MACD crosses below signal line
        bearish_cross = (~macd_above_signal) & macd_above_signal_prev
        signals[bearish_cross] = -1.0

        # Log signal summary
        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()
        hold_signals = (signals == 0.0).sum()

        logger.info(
            "Generated MACD signals - Buy: %d, Sell: %d, Hold: %d",
            buy_signals,
            sell_signals,
            hold_signals,
        )

        return signals
