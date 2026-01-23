"""Bollinger Bands Strategy.

This module implements a Bollinger Bands mean reversion strategy. It generates
buy signals when price touches the lower band and sell signals when price touches
the upper band, based on the assumption that prices tend to revert to the mean.

Bollinger Bands consist of:
- Upper band: SMA + (num_std * standard deviation)
- Middle band: Simple Moving Average
- Lower band: SMA - (num_std * standard deviation)
"""

import pandas as pd

from src.strategy.base import Strategy
from src.strategy.indicators import bollinger_bands
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BollingerBandsStrategy(Strategy):
    """Bollinger Bands Mean Reversion Strategy.

    Generates trading signals based on price position relative to Bollinger Bands:
    - Oversold: Price crosses below lower band (buy signal)
    - Overbought: Price crosses above upper band (sell signal)

    Signal Logic:
        - Buy (+1.0): Price crosses below lower band (oversold)
        - Sell (-1.0): Price crosses above upper band (overbought)
        - Hold (0.0): Price is within the bands or no crossover

    Parameters:
        - period (int): Period for moving average (default: 20)
        - num_std (float): Number of standard deviations (default: 2.0)
        - min_required_rows (int): Minimum data points needed (default: 100)

    Example:
        >>> from src.api.data_api import DataAPI
        >>> from src.strategy.bollinger_bands_strategy import BollingerBandsStrategy
        >>>
        >>> # Initialize strategy with default parameters
        >>> strategy = BollingerBandsStrategy({
        ...     'period': 20,
        ...     'num_std': 2.0
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
        if "period" not in self.params:
            raise ValueError("'period' parameter required")
        if "num_std" not in self.params:
            raise ValueError("'num_std' parameter required")

        # Validate parameter values
        if self.params["period"] < 1:
            raise ValueError("'period' must be positive")
        if self.params["num_std"] <= 0:
            raise ValueError("'num_std' must be positive")

        logger.debug(
            "Bollinger Bands params validated: period=%d, num_std=%.1f",
            self.params["period"],
            self.params["num_std"],
        )

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate Bollinger Bands.

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with original data plus 'bb_upper', 'bb_middle', 'bb_lower' columns
        """
        data = data.copy()

        # Calculate Bollinger Bands
        upper, middle, lower = bollinger_bands(
            data["close"],
            period=self.params["period"],
            num_std=self.params["num_std"],
        )

        data["bb_upper"] = upper
        data["bb_middle"] = middle
        data["bb_lower"] = lower

        logger.debug(
            "Calculated Bollinger Bands: period=%d, num_std=%.1f",
            self.params["period"],
            self.params["num_std"],
        )

        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on Bollinger Bands crossovers.

        Signal Generation Rules:
        1. Oversold Entry (Buy): Price crosses BELOW lower band
           - Current: close < bb_lower
           - Previous: close >= bb_lower
           - Signal: +1.0

        2. Overbought Exit (Sell): Price crosses ABOVE upper band
           - Current: close > bb_upper
           - Previous: close <= bb_upper
           - Signal: -1.0

        3. Within Bands (Hold): Price is between bands or no crossover
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

        # Detect crossovers
        close = data["close"]
        close_prev = close.shift(1)

        # Buy signal: Price crosses below lower band
        below_lower = (close < data["bb_lower"]) & (close_prev >= data["bb_lower"])
        signals[below_lower] = 1.0

        # Sell signal: Price crosses above upper band
        above_upper = (close > data["bb_upper"]) & (close_prev <= data["bb_upper"])
        signals[above_upper] = -1.0

        # Log signal summary
        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()
        hold_signals = (signals == 0.0).sum()

        logger.info(
            "Generated Bollinger Bands signals - Buy: %d, Sell: %d, Hold: %d",
            buy_signals,
            sell_signals,
            hold_signals,
        )

        return signals
