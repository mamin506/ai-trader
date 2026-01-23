"""RSI (Relative Strength Index) Strategy.

This module implements a classic RSI-based mean reversion strategy. It generates
buy signals when RSI indicates oversold conditions and sell signals when overbought.

The RSI oscillates between 0 and 100, traditionally:
- RSI < 30: Oversold (potential buy opportunity)
- RSI > 70: Overbought (potential sell opportunity)
"""

import pandas as pd

from src.strategy.base import Strategy
from src.strategy.indicators import rsi
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RSIStrategy(Strategy):
    """RSI Mean Reversion Strategy.

    Generates trading signals based on RSI overbought/oversold levels:
    - Oversold: RSI crosses below oversold_threshold (buy signal)
    - Overbought: RSI crosses above overbought_threshold (sell signal)

    Signal Logic:
        - Buy (+1.0): RSI crosses below oversold level (e.g., 30)
        - Sell (-1.0): RSI crosses above overbought level (e.g., 70)
        - Hold (0.0): RSI is in neutral zone or no crossover

    Parameters:
        - rsi_period (int): Period for RSI calculation (default: 14)
        - oversold_threshold (float): RSI level for oversold (default: 30)
        - overbought_threshold (float): RSI level for overbought (default: 70)
        - min_required_rows (int): Minimum data points needed (default: 100)

    Example:
        >>> from src.api.data_api import DataAPI
        >>> from src.strategy.rsi_strategy import RSIStrategy
        >>>
        >>> # Initialize strategy with custom thresholds
        >>> strategy = RSIStrategy({
        ...     'rsi_period': 14,
        ...     'oversold_threshold': 30,
        ...     'overbought_threshold': 70
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
        if "rsi_period" not in self.params:
            raise ValueError("'rsi_period' parameter required")
        if "oversold_threshold" not in self.params:
            raise ValueError("'oversold_threshold' parameter required")
        if "overbought_threshold" not in self.params:
            raise ValueError("'overbought_threshold' parameter required")

        # Validate parameter values
        if self.params["rsi_period"] < 1:
            raise ValueError("'rsi_period' must be positive")
        if not 0 <= self.params["oversold_threshold"] <= 100:
            raise ValueError("'oversold_threshold' must be between 0 and 100")
        if not 0 <= self.params["overbought_threshold"] <= 100:
            raise ValueError("'overbought_threshold' must be between 0 and 100")
        if self.params["oversold_threshold"] >= self.params["overbought_threshold"]:
            raise ValueError("'oversold_threshold' must be less than 'overbought_threshold'")

        logger.debug(
            "RSI params validated: period=%d, oversold=%.1f, overbought=%.1f",
            self.params["rsi_period"],
            self.params["oversold_threshold"],
            self.params["overbought_threshold"],
        )

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI indicator.

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with original data plus 'rsi' column
        """
        data = data.copy()

        # Calculate RSI
        data["rsi"] = rsi(data["close"], period=self.params["rsi_period"])

        logger.debug(
            "Calculated RSI with period=%d",
            self.params["rsi_period"],
        )

        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on RSI levels.

        Signal Generation Rules:
        1. Oversold Entry (Buy): RSI crosses BELOW oversold threshold
           - Current: rsi < oversold_threshold
           - Previous: rsi >= oversold_threshold
           - Signal: +1.0

        2. Overbought Exit (Sell): RSI crosses ABOVE overbought threshold
           - Current: rsi > overbought_threshold
           - Previous: rsi <= overbought_threshold
           - Signal: -1.0

        3. Neutral Zone (Hold): RSI is between thresholds or no crossover
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

        # Get thresholds
        oversold = self.params["oversold_threshold"]
        overbought = self.params["overbought_threshold"]

        # Detect crossovers
        # Buy signal: RSI crosses below oversold threshold
        rsi_values = data["rsi"]
        rsi_prev = rsi_values.shift(1)

        # Oversold crossover (buy signal)
        oversold_cross = (rsi_values < oversold) & (rsi_prev >= oversold)
        signals[oversold_cross] = 1.0

        # Overbought crossover (sell signal)
        overbought_cross = (rsi_values > overbought) & (rsi_prev <= overbought)
        signals[overbought_cross] = -1.0

        # Log signal summary
        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()
        hold_signals = (signals == 0.0).sum()

        logger.info(
            "Generated RSI signals - Buy: %d, Sell: %d, Hold: %d",
            buy_signals,
            sell_signals,
            hold_signals,
        )

        return signals
