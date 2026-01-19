"""Unit tests for technical indicator utilities."""

import numpy as np
import pandas as pd
import pytest

from src.strategy.indicators import (
    adx,
    atr,
    bollinger_bands,
    ema,
    macd,
    obv,
    roc,
    rsi,
    sma,
    stochastic,
)


class TestIndicators:
    """Test cases for TA-Lib indicator wrappers."""

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        np.random.seed(42)

        # Generate realistic price data
        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.abs(np.random.randn(100) * 1)
        low = close - np.abs(np.random.randn(100) * 1)
        open_price = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1000000, 5000000, 100)

        return pd.DataFrame(
            {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    def test_sma_basic(self, sample_data: pd.DataFrame) -> None:
        """Test SMA calculation returns correct structure."""
        result = sma(sample_data["close"], period=20)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "sma_20"
        # First 19 values should be NaN (not enough data)
        assert result.iloc[:19].isna().all()
        # After period, values should be present
        assert not result.iloc[19:].isna().all()

    def test_sma_values(self, sample_data: pd.DataFrame) -> None:
        """Test SMA calculation produces expected values."""
        result = sma(sample_data["close"], period=5)

        # Manually calculate SMA for verification
        expected = sample_data["close"].rolling(window=5).mean()

        # Compare non-NaN values
        pd.testing.assert_series_equal(
            result.dropna(), expected.dropna(), check_names=False
        )

    def test_ema_basic(self, sample_data: pd.DataFrame) -> None:
        """Test EMA calculation returns correct structure."""
        result = ema(sample_data["close"], period=12)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "ema_12"

    def test_ema_differs_from_sma(self, sample_data: pd.DataFrame) -> None:
        """Test EMA gives different values than SMA."""
        sma_result = sma(sample_data["close"], period=20)
        ema_result = ema(sample_data["close"], period=20)

        # EMA and SMA should differ (EMA weights recent prices more)
        non_nan_idx = ~sma_result.isna() & ~ema_result.isna()
        assert not (sma_result[non_nan_idx] == ema_result[non_nan_idx]).all()

    def test_rsi_basic(self, sample_data: pd.DataFrame) -> None:
        """Test RSI calculation returns correct structure."""
        result = rsi(sample_data["close"], period=14)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "rsi_14"

    def test_rsi_range(self, sample_data: pd.DataFrame) -> None:
        """Test RSI values are in valid range [0, 100]."""
        result = rsi(sample_data["close"], period=14)

        # RSI should be between 0 and 100
        valid_values = result.dropna()
        assert valid_values.min() >= 0
        assert valid_values.max() <= 100

    def test_macd_basic(self, sample_data: pd.DataFrame) -> None:
        """Test MACD calculation returns three series."""
        macd_line, signal_line, histogram = macd(sample_data["close"])

        assert isinstance(macd_line, pd.Series)
        assert isinstance(signal_line, pd.Series)
        assert isinstance(histogram, pd.Series)

        assert len(macd_line) == len(sample_data)
        assert len(signal_line) == len(sample_data)
        assert len(histogram) == len(sample_data)

        assert macd_line.name == "macd"
        assert signal_line.name == "macd_signal"
        assert histogram.name == "macd_histogram"

    def test_macd_histogram_relationship(self, sample_data: pd.DataFrame) -> None:
        """Test MACD histogram is difference between MACD and signal."""
        macd_line, signal_line, histogram = macd(sample_data["close"])

        # Histogram should be MACD - Signal (approximately, accounting for NaN)
        valid_idx = ~macd_line.isna() & ~signal_line.isna()
        expected_histogram = macd_line[valid_idx] - signal_line[valid_idx]

        np.testing.assert_array_almost_equal(
            histogram[valid_idx].values, expected_histogram.values, decimal=10
        )

    def test_bollinger_bands_basic(self, sample_data: pd.DataFrame) -> None:
        """Test Bollinger Bands calculation returns three series."""
        upper, middle, lower = bollinger_bands(sample_data["close"], period=20)

        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)

        assert len(upper) == len(sample_data)
        assert upper.name == "bb_upper_20"
        assert middle.name == "bb_middle_20"
        assert lower.name == "bb_lower_20"

    def test_bollinger_bands_relationship(self, sample_data: pd.DataFrame) -> None:
        """Test Bollinger Bands maintain upper > middle > lower."""
        upper, middle, lower = bollinger_bands(sample_data["close"], period=20)

        valid_idx = ~upper.isna() & ~middle.isna() & ~lower.isna()

        # Upper should be >= middle >= lower
        assert (upper[valid_idx] >= middle[valid_idx]).all()
        assert (middle[valid_idx] >= lower[valid_idx]).all()

    def test_atr_basic(self, sample_data: pd.DataFrame) -> None:
        """Test ATR calculation returns correct structure."""
        result = atr(
            sample_data["high"], sample_data["low"], sample_data["close"], period=14
        )

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "atr_14"

    def test_atr_positive_values(self, sample_data: pd.DataFrame) -> None:
        """Test ATR values are positive (volatility measure)."""
        result = atr(
            sample_data["high"], sample_data["low"], sample_data["close"], period=14
        )

        valid_values = result.dropna()
        assert (valid_values >= 0).all()

    def test_stochastic_basic(self, sample_data: pd.DataFrame) -> None:
        """Test Stochastic oscillator returns two series."""
        slowk, slowd = stochastic(
            sample_data["high"], sample_data["low"], sample_data["close"]
        )

        assert isinstance(slowk, pd.Series)
        assert isinstance(slowd, pd.Series)
        assert len(slowk) == len(sample_data)
        assert len(slowd) == len(sample_data)
        assert slowk.name == "stoch_k"
        assert slowd.name == "stoch_d"

    def test_stochastic_range(self, sample_data: pd.DataFrame) -> None:
        """Test Stochastic values are in range [0, 100]."""
        slowk, slowd = stochastic(
            sample_data["high"], sample_data["low"], sample_data["close"]
        )

        valid_k = slowk.dropna()
        valid_d = slowd.dropna()

        assert valid_k.min() >= 0
        assert valid_k.max() <= 100
        assert valid_d.min() >= 0
        assert valid_d.max() <= 100

    def test_adx_basic(self, sample_data: pd.DataFrame) -> None:
        """Test ADX calculation returns correct structure."""
        result = adx(
            sample_data["high"], sample_data["low"], sample_data["close"], period=14
        )

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "adx_14"

    def test_adx_range(self, sample_data: pd.DataFrame) -> None:
        """Test ADX values are in valid range [0, 100]."""
        result = adx(
            sample_data["high"], sample_data["low"], sample_data["close"], period=14
        )

        valid_values = result.dropna()
        assert valid_values.min() >= 0
        assert valid_values.max() <= 100

    def test_obv_basic(self, sample_data: pd.DataFrame) -> None:
        """Test OBV calculation returns correct structure."""
        result = obv(sample_data["close"], sample_data["volume"])

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "obv"

    def test_obv_cumulative(self, sample_data: pd.DataFrame) -> None:
        """Test OBV is cumulative (changes based on price direction)."""
        result = obv(sample_data["close"], sample_data["volume"])

        # OBV should have no NaN values (starts from first value)
        assert not result.isna().any()

        # OBV changes should relate to volume
        obv_changes = result.diff().dropna()
        assert len(obv_changes) > 0

    def test_roc_basic(self, sample_data: pd.DataFrame) -> None:
        """Test ROC calculation returns correct structure."""
        result = roc(sample_data["close"], period=10)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert result.name == "roc_10"

    def test_roc_percentage(self, sample_data: pd.DataFrame) -> None:
        """Test ROC represents percentage change."""
        result = roc(sample_data["close"], period=10)

        # ROC should be NaN for first 10 values
        assert result.iloc[:10].isna().all()

        # ROC values should be reasonable percentages (not 0-1 range, but percentage points)
        valid_values = result.dropna()
        # Typically ROC ranges from -50% to +50% for daily data
        assert valid_values.min() > -100
        assert valid_values.max() < 100

    def test_indicators_preserve_index(self, sample_data: pd.DataFrame) -> None:
        """Test all indicators preserve the original index."""
        close = sample_data["close"]

        # Test single-series indicators
        sma_result = sma(close, period=20)
        ema_result = ema(close, period=20)
        rsi_result = rsi(close, period=14)

        pd.testing.assert_index_equal(sma_result.index, sample_data.index)
        pd.testing.assert_index_equal(ema_result.index, sample_data.index)
        pd.testing.assert_index_equal(rsi_result.index, sample_data.index)

    def test_indicators_handle_different_periods(
        self, sample_data: pd.DataFrame
    ) -> None:
        """Test indicators can handle different period parameters."""
        close = sample_data["close"]

        # Test various periods
        for period in [5, 10, 20, 50]:
            sma_result = sma(close, period=period)
            assert isinstance(sma_result, pd.Series)
            assert len(sma_result) == len(close)
