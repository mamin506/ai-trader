"""Technical indicator utilities using TA-Lib.

This module provides wrapper functions for common TA-Lib indicators,
simplifying their usage in trading strategies.

Note: TA-Lib is required. Install with: pip install TA-Lib
"""

from typing import Tuple

import numpy as np
import pandas as pd
import talib

from src.utils.logging import get_logger

logger = get_logger(__name__)


def sma(data: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average.

    Args:
        data: Price series (typically 'close')
        period: Number of periods for moving average

    Returns:
        Series containing SMA values

    Example:
        >>> close_prices = data['close']
        >>> sma_20 = sma(close_prices, period=20)
    """
    result = talib.SMA(data.values, timeperiod=period)
    return pd.Series(result, index=data.index, name=f"sma_{period}")


def ema(data: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        data: Price series (typically 'close')
        period: Number of periods for moving average

    Returns:
        Series containing EMA values

    Example:
        >>> close_prices = data['close']
        >>> ema_12 = ema(close_prices, period=12)
    """
    result = talib.EMA(data.values, timeperiod=period)
    return pd.Series(result, index=data.index, name=f"ema_{period}")


def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index.

    Args:
        data: Price series (typically 'close')
        period: Number of periods for RSI calculation (default: 14)

    Returns:
        Series containing RSI values (0-100 range)

    Example:
        >>> close_prices = data['close']
        >>> rsi_14 = rsi(close_prices, period=14)
        >>> overbought = rsi_14 > 70
        >>> oversold = rsi_14 < 30
    """
    result = talib.RSI(data.values, timeperiod=period)
    return pd.Series(result, index=data.index, name=f"rsi_{period}")


def macd(
    data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD (Moving Average Convergence Divergence).

    Args:
        data: Price series (typically 'close')
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        Tuple of (macd_line, signal_line, histogram)

    Example:
        >>> close_prices = data['close']
        >>> macd_line, signal_line, histogram = macd(close_prices)
        >>> bullish_crossover = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    """
    macd_line, signal_line, histogram = talib.MACD(
        data.values,
        fastperiod=fast_period,
        slowperiod=slow_period,
        signalperiod=signal_period,
    )

    return (
        pd.Series(macd_line, index=data.index, name="macd"),
        pd.Series(signal_line, index=data.index, name="macd_signal"),
        pd.Series(histogram, index=data.index, name="macd_histogram"),
    )


def bollinger_bands(
    data: pd.Series, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands.

    Args:
        data: Price series (typically 'close')
        period: Number of periods for moving average (default: 20)
        num_std: Number of standard deviations (default: 2.0)

    Returns:
        Tuple of (upper_band, middle_band, lower_band)

    Example:
        >>> close_prices = data['close']
        >>> upper, middle, lower = bollinger_bands(close_prices, period=20, num_std=2)
        >>> above_upper = close_prices > upper  # Overbought signal
        >>> below_lower = close_prices < lower  # Oversold signal
    """
    upper, middle, lower = talib.BBANDS(
        data.values, timeperiod=period, nbdevup=num_std, nbdevdn=num_std, matype=0
    )

    return (
        pd.Series(upper, index=data.index, name=f"bb_upper_{period}"),
        pd.Series(middle, index=data.index, name=f"bb_middle_{period}"),
        pd.Series(lower, index=data.index, name=f"bb_lower_{period}"),
    )


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Calculate Average True Range (volatility indicator).

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: Number of periods for ATR calculation (default: 14)

    Returns:
        Series containing ATR values

    Example:
        >>> atr_14 = atr(data['high'], data['low'], data['close'], period=14)
        >>> high_volatility = atr_14 > atr_14.rolling(50).mean()
    """
    result = talib.ATR(high.values, low.values, close.values, timeperiod=period)
    return pd.Series(result, index=close.index, name=f"atr_{period}")


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    fastk_period: int = 14,
    slowk_period: int = 3,
    slowd_period: int = 3,
) -> Tuple[pd.Series, pd.Series]:
    """Calculate Stochastic Oscillator.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        fastk_period: Fast %K period (default: 14)
        slowk_period: Slow %K period (default: 3)
        slowd_period: Slow %D period (default: 3)

    Returns:
        Tuple of (slowk, slowd)

    Example:
        >>> slowk, slowd = stochastic(data['high'], data['low'], data['close'])
        >>> overbought = slowk > 80
        >>> oversold = slowk < 20
    """
    slowk, slowd = talib.STOCH(
        high.values,
        low.values,
        close.values,
        fastk_period=fastk_period,
        slowk_period=slowk_period,
        slowd_period=slowd_period,
    )

    return (
        pd.Series(slowk, index=close.index, name="stoch_k"),
        pd.Series(slowd, index=close.index, name="stoch_d"),
    )


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Calculate Average Directional Index (trend strength indicator).

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: Number of periods for ADX calculation (default: 14)

    Returns:
        Series containing ADX values (0-100, >25 indicates strong trend)

    Example:
        >>> adx_14 = adx(data['high'], data['low'], data['close'], period=14)
        >>> strong_trend = adx_14 > 25
        >>> weak_trend = adx_14 < 20
    """
    result = talib.ADX(high.values, low.values, close.values, timeperiod=period)
    return pd.Series(result, index=close.index, name=f"adx_{period}")


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume (volume-based momentum indicator).

    Args:
        close: Close price series
        volume: Volume series

    Returns:
        Series containing OBV values

    Example:
        >>> obv_values = obv(data['close'], data['volume'])
        >>> obv_trend = obv_values > obv_values.rolling(20).mean()
    """
    # Convert volume to float64 (TA-Lib requires double type)
    result = talib.OBV(close.values, volume.astype(np.float64).values)
    return pd.Series(result, index=close.index, name="obv")


def roc(data: pd.Series, period: int = 10) -> pd.Series:
    """Calculate Rate of Change (momentum indicator).

    Args:
        data: Price series (typically 'close')
        period: Number of periods for ROC calculation (default: 10)

    Returns:
        Series containing ROC values (percentage change)

    Example:
        >>> roc_10 = roc(data['close'], period=10)
        >>> positive_momentum = roc_10 > 0
    """
    result = talib.ROC(data.values, timeperiod=period)
    return pd.Series(result, index=data.index, name=f"roc_{period}")
