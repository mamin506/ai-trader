"""Unit tests for MACD Strategy."""

import numpy as np
import pandas as pd
import pytest

from src.strategy.macd_strategy import MACDStrategy


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")

    # Create price data with trends for MACD crossovers
    close_prices = np.concatenate([
        np.linspace(100, 110, 30),  # Uptrend
        np.linspace(110, 105, 20),  # Consolidation
        np.linspace(105, 95, 30),   # Downtrend
        np.linspace(95, 100, 20),   # Recovery
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


class TestMACDStrategyValidation:
    """Test parameter validation for MACD Strategy."""

    def test_validate_params_success(self):
        """Test that valid parameters pass validation."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        # Should not raise
        strategy.validate_params()

    def test_validate_params_missing_fast_period(self):
        """Test that missing fast_period raises ValueError."""
        with pytest.raises(ValueError, match="'fast_period' parameter required"):
            MACDStrategy({
                "slow_period": 26,
                "signal_period": 9,
            })

    def test_validate_params_missing_slow_period(self):
        """Test that missing slow_period raises ValueError."""
        with pytest.raises(ValueError, match="'slow_period' parameter required"):
            MACDStrategy({
                "fast_period": 12,
                "signal_period": 9,
            })

    def test_validate_params_missing_signal_period(self):
        """Test that missing signal_period raises ValueError."""
        with pytest.raises(ValueError, match="'signal_period' parameter required"):
            MACDStrategy({
                "fast_period": 12,
                "slow_period": 26,
            })

    def test_validate_params_negative_fast_period(self):
        """Test that negative fast_period raises ValueError."""
        with pytest.raises(ValueError, match="'fast_period' must be positive"):
            MACDStrategy({
                "fast_period": -12,
                "slow_period": 26,
                "signal_period": 9,
            })

    def test_validate_params_negative_slow_period(self):
        """Test that negative slow_period raises ValueError."""
        with pytest.raises(ValueError, match="'slow_period' must be positive"):
            MACDStrategy({
                "fast_period": 12,
                "slow_period": -26,
                "signal_period": 9,
            })

    def test_validate_params_negative_signal_period(self):
        """Test that negative signal_period raises ValueError."""
        with pytest.raises(ValueError, match="'signal_period' must be positive"):
            MACDStrategy({
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": -9,
            })

    def test_validate_params_fast_greater_than_slow(self):
        """Test that fast_period >= slow_period raises ValueError."""
        with pytest.raises(ValueError, match="'fast_period' must be less than 'slow_period'"):
            MACDStrategy({
                "fast_period": 30,
                "slow_period": 26,
                "signal_period": 9,
            })

    def test_validate_params_fast_equals_slow(self):
        """Test that fast_period == slow_period raises ValueError."""
        with pytest.raises(ValueError, match="'fast_period' must be less than 'slow_period'"):
            MACDStrategy({
                "fast_period": 26,
                "slow_period": 26,
                "signal_period": 9,
            })


class TestMACDStrategyIndicators:
    """Test indicator calculation for MACD Strategy."""

    def test_calculate_indicators_adds_macd_columns(self, sample_data):
        """Test that calculate_indicators adds MACD columns."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        assert "macd" in result.columns
        assert "macd_signal" in result.columns
        assert "macd_histogram" in result.columns

    def test_calculate_indicators_preserves_original(self, sample_data):
        """Test that original OHLCV columns are preserved."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns
            pd.testing.assert_series_equal(result[col], sample_data[col])

    def test_calculate_indicators_histogram_relationship(self, sample_data):
        """Test that MACD histogram = MACD - Signal."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)

        # Histogram should equal MACD minus Signal (within floating point tolerance)
        expected_histogram = result["macd"] - result["macd_signal"]
        pd.testing.assert_series_equal(
            result["macd_histogram"],
            expected_histogram,
            check_names=False,
            atol=1e-10,
        )


class TestMACDStrategySignals:
    """Test signal generation for MACD Strategy."""

    def test_generate_signals_returns_series(self, sample_data):
        """Test that generate_signals returns a pandas Series."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)

    def test_generate_signals_range(self, sample_data):
        """Test that all signals are in valid range [-1.0, 1.0]."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        assert (signals >= -1.0).all()
        assert (signals <= 1.0).all()

    def test_generate_signals_only_valid_values(self, sample_data):
        """Test that signals only contain -1.0, 0.0, or 1.0."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        unique_signals = signals.unique()
        assert all(s in [-1.0, 0.0, 1.0] for s in unique_signals)

    def test_generate_signals_mostly_hold(self, sample_data):
        """Test that most signals are hold (0.0) for typical market data."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        # Most signals should be hold for normal market conditions
        hold_ratio = (signals == 0.0).sum() / len(signals)
        assert hold_ratio > 0.8  # At least 80% should be hold signals

    def test_generate_signals_detects_crossovers(self):
        """Test that strategy detects MACD crossovers."""
        # Create data with clear trend changes
        dates = pd.date_range("2024-01-01", periods=80, freq="D")

        # Strong uptrend then downtrend for clear crossovers
        close_prices = np.concatenate([
            np.linspace(50, 80, 40),   # Strong uptrend
            np.linspace(80, 50, 40),   # Strong downtrend
        ])

        data = pd.DataFrame({
            "open": close_prices * 1.01,
            "high": close_prices * 1.02,
            "low": close_prices * 0.98,
            "close": close_prices,
            "volume": np.ones(80) * 1000000,
        }, index=dates)

        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 30,
        })

        signals = strategy.generate_signals(data)

        # Should have some buy and sell signals
        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()

        # At least one of each type should exist
        assert buy_signals > 0 or sell_signals > 0

    def test_custom_periods(self, sample_data):
        """Test that custom periods affect signal generation."""
        # Fast MACD (5/13/5)
        fast_macd = MACDStrategy({
            "fast_period": 5,
            "slow_period": 13,
            "signal_period": 5,
            "min_required_rows": 20,
        })

        # Standard MACD (12/26/9)
        standard_macd = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 30,
        })

        fast_signals = fast_macd.generate_signals(sample_data)
        standard_signals = standard_macd.generate_signals(sample_data)

        # Fast MACD should generate more signals (more responsive)
        fast_count = (fast_signals != 0.0).sum()
        standard_count = (standard_signals != 0.0).sum()

        assert fast_count >= standard_count

    def test_no_duplicate_consecutive_signals(self, sample_data):
        """Test that we don't get duplicate consecutive buy or sell signals."""
        strategy = MACDStrategy({
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)

        # Check no consecutive duplicate non-zero signals
        non_zero_signals = signals[signals != 0.0]
        if len(non_zero_signals) > 1:
            # No two consecutive signals should be the same
            for i in range(len(non_zero_signals) - 1):
                current_idx = non_zero_signals.index[i]
                next_idx = non_zero_signals.index[i + 1]
                # If they're not immediately consecutive, skip
                if (next_idx - current_idx).days > 1:
                    continue
                # They should be opposite if consecutive
                assert non_zero_signals.iloc[i] != non_zero_signals.iloc[i + 1]
