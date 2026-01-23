"""Unit tests for RSI Strategy."""

import numpy as np
import pandas as pd
import pytest

from src.strategy.rsi_strategy import RSIStrategy


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")

    # Create price data that will generate clear RSI signals
    # Simulate oversold and overbought conditions
    close_prices = np.concatenate([
        np.linspace(100, 80, 20),   # Downtrend (RSI will drop)
        np.linspace(80, 100, 20),   # Uptrend (RSI will rise)
        np.linspace(100, 70, 20),   # Sharp drop (RSI oversold)
        np.linspace(70, 110, 20),   # Sharp rise (RSI overbought)
        np.linspace(110, 90, 20),   # Moderate decline
    ])

    data = pd.DataFrame(
        {
            "open": close_prices * 1.01,
            "high": close_prices * 1.02,
            "low": close_prices * 0.98,
            "close": close_prices,
            "volume": np.random.randint(1000000, 5000000, len(dates)),
        },
        index=dates,
    )
    return data


class TestRSIStrategyValidation:
    """Test parameter validation for RSI Strategy."""

    def test_validate_params_success(self):
        """Test that valid parameters pass validation."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        # Should not raise
        strategy.validate_params()

    def test_validate_params_missing_rsi_period(self):
        """Test that missing rsi_period raises ValueError."""
        with pytest.raises(ValueError, match="'rsi_period' parameter required"):
            RSIStrategy({
                "oversold_threshold": 30,
                "overbought_threshold": 70,
            })

    def test_validate_params_missing_oversold_threshold(self):
        """Test that missing oversold_threshold raises ValueError."""
        with pytest.raises(ValueError, match="'oversold_threshold' parameter required"):
            RSIStrategy({
                "rsi_period": 14,
                "overbought_threshold": 70,
            })

    def test_validate_params_missing_overbought_threshold(self):
        """Test that missing overbought_threshold raises ValueError."""
        with pytest.raises(ValueError, match="'overbought_threshold' parameter required"):
            RSIStrategy({
                "rsi_period": 14,
                "oversold_threshold": 30,
            })

    def test_validate_params_negative_period(self):
        """Test that negative rsi_period raises ValueError."""
        with pytest.raises(ValueError, match="'rsi_period' must be positive"):
            RSIStrategy({
                "rsi_period": -5,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
            })

    def test_validate_params_invalid_oversold_threshold(self):
        """Test that oversold_threshold outside 0-100 raises ValueError."""
        with pytest.raises(ValueError, match="'oversold_threshold' must be between 0 and 100"):
            RSIStrategy({
                "rsi_period": 14,
                "oversold_threshold": -10,
                "overbought_threshold": 70,
            })

    def test_validate_params_invalid_overbought_threshold(self):
        """Test that overbought_threshold outside 0-100 raises ValueError."""
        with pytest.raises(ValueError, match="'overbought_threshold' must be between 0 and 100"):
            RSIStrategy({
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 110,
            })

    def test_validate_params_oversold_greater_than_overbought(self):
        """Test that oversold >= overbought raises ValueError."""
        with pytest.raises(ValueError, match="'oversold_threshold' must be less than 'overbought_threshold'"):
            RSIStrategy({
                "rsi_period": 14,
                "oversold_threshold": 80,
                "overbought_threshold": 70,
            })


class TestRSIStrategyIndicators:
    """Test indicator calculation for RSI Strategy."""

    def test_calculate_indicators_adds_rsi_column(self, sample_data):
        """Test that calculate_indicators adds 'rsi' column."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        assert "rsi" in result.columns

    def test_calculate_indicators_preserves_original(self, sample_data):
        """Test that original OHLCV columns are preserved."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns
            pd.testing.assert_series_equal(result[col], sample_data[col])

    def test_calculate_indicators_rsi_range(self, sample_data):
        """Test that RSI values are in valid range (0-100)."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        rsi_values = result["rsi"].dropna()
        assert (rsi_values >= 0).all()
        assert (rsi_values <= 100).all()


class TestRSIStrategySignals:
    """Test signal generation for RSI Strategy."""

    def test_generate_signals_returns_series(self, sample_data):
        """Test that generate_signals returns a pandas Series."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)

    def test_generate_signals_range(self, sample_data):
        """Test that all signals are in valid range [-1.0, 1.0]."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        assert (signals >= -1.0).all()
        assert (signals <= 1.0).all()

    def test_generate_signals_only_valid_values(self, sample_data):
        """Test that signals only contain -1.0, 0.0, or 1.0."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        unique_signals = signals.unique()
        assert all(s in [-1.0, 0.0, 1.0] for s in unique_signals)

    def test_generate_signals_mostly_hold(self, sample_data):
        """Test that most signals are hold (0.0) for typical market data."""
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        # Most signals should be hold for normal market conditions
        hold_ratio = (signals == 0.0).sum() / len(signals)
        assert hold_ratio > 0.5  # At least 50% should be hold signals

    def test_custom_thresholds(self, sample_data):
        """Test that custom thresholds affect signal generation."""
        # More conservative thresholds (20/80)
        conservative = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 20,
            "overbought_threshold": 80,
            "min_required_rows": 50,
        })

        # More aggressive thresholds (40/60)
        aggressive = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 40,
            "overbought_threshold": 60,
            "min_required_rows": 50,
        })

        conservative_signals = conservative.generate_signals(sample_data)
        aggressive_signals = aggressive.generate_signals(sample_data)

        # Aggressive should generate more signals
        conservative_count = (conservative_signals != 0.0).sum()
        aggressive_count = (aggressive_signals != 0.0).sum()

        assert aggressive_count >= conservative_count
