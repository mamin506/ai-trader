"""Abstract base class for trading strategies.

This module defines the contract for all strategy implementations in the AI Trader system.
Strategies analyze market data and generate trading signals without knowledge of portfolio
allocation or risk management.
"""

from abc import ABC, abstractmethod
from typing import Dict

import pandas as pd


class Strategy(ABC):
    """Abstract base class for all trading strategies.

    Each strategy analyzes market data and outputs directional signals
    with confidence scores, without knowledge of portfolio allocation.

    Signal Semantics:
        Signals are float values in range [-1.0, 1.0] where:
        - Sign represents direction: positive = buy, negative = sell
        - Magnitude represents confidence: 0.0 = neutral, 1.0 = maximum conviction
        - Examples:
            +1.0: Strong buy signal
            +0.5: Moderate buy signal
            0.0: Neutral (hold)
            -0.5: Moderate sell signal
            -1.0: Strong sell signal

    Design Principles:
        - Strategy generates SIGNALS only, not position sizes
        - Strategy operates independently per symbol
        - Portfolio Management Layer aggregates signals and allocates capital
        - Risk Management Layer enforces position limits

    Example:
        >>> class SimpleMA(Strategy):
        ...     def validate_params(self):
        ...         assert 'period' in self.params
        ...     def calculate_indicators(self, data):
        ...         data['ma'] = data['close'].rolling(self.params['period']).mean()
        ...         return data
        ...     def generate_signals(self, data):
        ...         # Buy when price > MA, sell when price < MA
        ...         signals = pd.Series(0.0, index=data.index)
        ...         signals[data['close'] > data['ma']] = 1.0
        ...         signals[data['close'] < data['ma']] = -1.0
        ...         return signals
    """

    def __init__(self, params: Dict):
        """Initialize strategy with parameters.

        Args:
            params: Strategy-specific parameters (e.g., {'fast_period': 20, 'slow_period': 50})
        """
        self.params = params
        self.validate_params()

    @abstractmethod
    def validate_params(self) -> None:
        """Validate that required parameters are present and valid.

        Raises:
            ValueError: If required parameters are missing or invalid

        Example:
            >>> def validate_params(self):
            ...     if 'period' not in self.params:
            ...         raise ValueError("'period' parameter required")
            ...     if self.params['period'] < 1:
            ...         raise ValueError("'period' must be positive")
        """
        pass

    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators needed for signal generation.

        This method is separated from signal generation to enable debugging
        and inspection of intermediate indicator values.

        Args:
            data: OHLCV DataFrame from DataProvider
                  Required columns: [open, high, low, close, volume]
                  Index: DatetimeIndex with name 'date'

        Returns:
            DataFrame with original OHLCV data plus additional indicator columns

        Example:
            >>> def calculate_indicators(self, data):
            ...     data = data.copy()
            ...     data['sma_20'] = data['close'].rolling(20).mean()
            ...     data['sma_50'] = data['close'].rolling(50).mean()
            ...     return data
        """
        pass

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on market data.

        This is the core strategy logic that produces directional signals
        with confidence levels.

        Args:
            data: OHLCV DataFrame (from DataProvider)
                  Required columns: [open, high, low, close, volume]
                  Index: DatetimeIndex with name 'date'

        Returns:
            Series: Signal values in range [-1.0, 1.0]
                   Index: timestamps (matching input data index)
                   Values: Direction + Confidence
                          +1.0 = strong buy
                          0.0 = neutral/hold
                          -1.0 = strong sell

        Example:
            >>> def generate_signals(self, data):
            ...     data = self.calculate_indicators(data)
            ...     signals = pd.Series(0.0, index=data.index)
            ...     # Buy when fast MA crosses above slow MA
            ...     signals[data['sma_20'] > data['sma_50']] = 1.0
            ...     # Sell when fast MA crosses below slow MA
            ...     signals[data['sma_20'] < data['sma_50']] = -1.0
            ...     return signals
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data quality before processing.

        Default implementation checks for:
        - Sufficient data points (based on min_required_rows parameter)
        - No missing values in critical OHLCV columns
        - DatetimeIndex with name 'date'

        Subclasses can override for custom validation logic.

        Args:
            data: OHLCV DataFrame to validate

        Returns:
            True if data passes validation, False otherwise

        Example:
            >>> strategy = SimpleMA({'period': 20, 'min_required_rows': 50})
            >>> data = api.get_daily_bars('AAPL', '2024-01-01', '2024-02-01')
            >>> if strategy.validate_data(data):
            ...     signals = strategy.generate_signals(data)
        """
        # Check minimum data points
        required_rows = self.params.get("min_required_rows", 100)
        if len(data) < required_rows:
            return False

        # Check for required columns
        required_columns = ["open", "high", "low", "close", "volume"]
        if not all(col in data.columns for col in required_columns):
            return False

        # Check for NaN in critical columns
        if data[required_columns].isna().sum().sum() > 0:
            return False

        # Check index is DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            return False

        return True
