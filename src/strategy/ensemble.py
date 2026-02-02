"""Multi-strategy ensemble for combining signals from multiple strategies.

This module implements a weighted ensemble approach to combine trading signals
from multiple strategies, providing more robust and diversified signal generation.
"""

from typing import Dict, List
import pandas as pd

from src.strategy.base import Strategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MultiStrategyEnsemble:
    """Ensemble of multiple strategies with weighted signal combination.

    Combines signals from multiple strategies using a weighted average approach.
    Each strategy contributes to the final signal based on its assigned weight.

    Signal Combination Formula:
        combined_signal = Σ(weight[i] * signal[i]) / Σ(weight[i])

    Example:
        >>> from src.strategy.ma_crossover import MACrossoverStrategy
        >>> from src.strategy.rsi_strategy import RSIStrategy
        >>>
        >>> strategies = [
        ...     MACrossoverStrategy({'fast_period': 20, 'slow_period': 50}),
        ...     RSIStrategy({'rsi_period': 14, 'oversold_threshold': 30, 'overbought_threshold': 70})
        ... ]
        >>> weights = [1.0, 1.0]  # Equal weighting
        >>>
        >>> ensemble = MultiStrategyEnsemble(strategies, weights)
        >>> signal = ensemble.get_latest_signal('AAPL', data)
    """

    def __init__(self, strategies: List[Strategy], weights: List[float] = None):
        """Initialize ensemble with strategies and weights.

        Args:
            strategies: List of Strategy instances to combine
            weights: List of weights for each strategy (default: equal weights)

        Raises:
            ValueError: If strategies is empty or weights length doesn't match
        """
        if not strategies:
            raise ValueError("At least one strategy is required")

        if weights is None:
            # Default to equal weights
            weights = [1.0] * len(strategies)

        if len(strategies) != len(weights):
            raise ValueError(
                f"Number of strategies ({len(strategies)}) must match "
                f"number of weights ({len(weights)})"
            )

        if any(w <= 0 for w in weights):
            raise ValueError("All weights must be positive")

        self.strategies = strategies
        self.weights = weights
        self.total_weight = sum(weights)

        logger.info(
            "MultiStrategyEnsemble initialized with %d strategies (weights: %s)",
            len(strategies),
            weights,
        )

    def get_latest_signal(self, symbol: str, data: pd.DataFrame) -> float:
        """Get the latest combined signal for a symbol.

        Generates signals from all strategies and combines them using weighted average.
        Extracts the most recent signal from each strategy's time series.

        Args:
            symbol: Stock ticker symbol
            data: Historical OHLCV data for the symbol

        Returns:
            Combined signal in range [-1.0, 1.0]
            - Positive values: Buy signals
            - Negative values: Sell signals
            - Zero: Neutral/hold

        Raises:
            ValueError: If data is empty or missing required columns
        """
        if data is None or data.empty:
            raise ValueError(f"No data provided for {symbol}")

        signals = []
        valid_weights = []

        for strategy, weight in zip(self.strategies, self.weights):
            try:
                # Generate full time series of signals
                signal_series = strategy.generate_signals(data)

                if signal_series.empty:
                    logger.warning(
                        "Strategy %s returned empty signals for %s, skipping",
                        strategy.__class__.__name__,
                        symbol,
                    )
                    continue

                # Extract the latest signal
                latest_signal = float(signal_series.iloc[-1])

                # Validate signal is in range [-1, 1]
                if abs(latest_signal) > 1.0:
                    logger.warning(
                        "Strategy %s generated out-of-range signal %.2f for %s, clamping",
                        strategy.__class__.__name__,
                        latest_signal,
                        symbol,
                    )
                    latest_signal = max(-1.0, min(1.0, latest_signal))

                signals.append(latest_signal)
                valid_weights.append(weight)

                logger.debug(
                    "Strategy %s signal for %s: %.3f",
                    strategy.__class__.__name__,
                    symbol,
                    latest_signal,
                )

            except Exception as e:
                logger.error(
                    "Error generating signal from %s for %s: %s",
                    strategy.__class__.__name__,
                    symbol,
                    e,
                )
                # Skip this strategy and continue with others
                continue

        if not signals:
            logger.warning(
                "No valid signals generated for %s, returning neutral (0.0)",
                symbol,
            )
            return 0.0

        # Calculate weighted average
        weighted_sum = sum(s * w for s, w in zip(signals, valid_weights))
        total_valid_weight = sum(valid_weights)
        combined_signal = weighted_sum / total_valid_weight

        logger.info(
            "Combined signal for %s: %.3f (from %d strategies)",
            symbol,
            combined_signal,
            len(signals),
        )

        return combined_signal

    def get_signals_for_all(self, symbols: List[str], data_dict: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Get latest signals for multiple symbols.

        Convenience method to generate signals for a list of symbols.

        Args:
            symbols: List of stock ticker symbols
            data_dict: Dictionary mapping symbol -> historical OHLCV data

        Returns:
            Dictionary mapping symbol -> combined signal
            Symbols with errors or missing data will have signal = 0.0

        Example:
            >>> data_dict = {
            ...     'AAPL': aapl_dataframe,
            ...     'MSFT': msft_dataframe
            ... }
            >>> signals = ensemble.get_signals_for_all(['AAPL', 'MSFT'], data_dict)
            >>> # {'AAPL': 0.65, 'MSFT': -0.23}
        """
        signals = {}

        for symbol in symbols:
            if symbol not in data_dict:
                logger.warning("No data available for %s, setting signal to 0.0", symbol)
                signals[symbol] = 0.0
                continue

            try:
                signal = self.get_latest_signal(symbol, data_dict[symbol])
                signals[symbol] = signal
            except Exception as e:
                logger.error("Error generating signal for %s: %s", symbol, e)
                signals[symbol] = 0.0

        return signals

    def get_strategy_details(self) -> List[Dict]:
        """Get details about each strategy in the ensemble.

        Returns:
            List of dictionaries with strategy class name, parameters, and weight
        """
        details = []
        for strategy, weight in zip(self.strategies, self.weights):
            details.append({
                'class': strategy.__class__.__name__,
                'params': strategy.params,
                'weight': weight,
                'weight_pct': (weight / self.total_weight) * 100
            })
        return details

    def __repr__(self) -> str:
        """String representation of the ensemble."""
        strategy_names = [s.__class__.__name__ for s in self.strategies]
        return f"MultiStrategyEnsemble(strategies={strategy_names}, weights={self.weights})"
