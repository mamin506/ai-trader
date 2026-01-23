"""Unit tests for Bollinger Bands Strategy."""

import numpy as np
import pandas as pd
import pytest

from src.strategy.bollinger_bands_strategy import BollingerBandsStrategy


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")

    # Create price data with volatility for Bollinger Bands
    np.random.seed(42)
    base_prices = np.linspace(100, 105, 100)
    noise = np.random.normal(0, 2, 100)  # Add volatility
    close_prices = base_prices + noise

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


class TestBollingerBandsStrategyValidation:
    """Test parameter validation for Bollinger Bands Strategy."""

    def test_validate_params_success(self):
        """Test that valid parameters pass validation."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        # Should not raise
        strategy.validate_params()

    def test_validate_params_missing_period(self):
        """Test that missing period raises ValueError."""
        with pytest.raises(ValueError, match="'period' parameter required"):
            BollingerBandsStrategy({
                "num_std": 2.0,
            })

    def test_validate_params_missing_num_std(self):
        """Test that missing num_std raises ValueError."""
        with pytest.raises(ValueError, match="'num_std' parameter required"):
            BollingerBandsStrategy({
                "period": 20,
            })

    def test_validate_params_negative_period(self):
        """Test that negative period raises ValueError."""
        with pytest.raises(ValueError, match="'period' must be positive"):
            BollingerBandsStrategy({
                "period": -20,
                "num_std": 2.0,
            })

    def test_validate_params_zero_period(self):
        """Test that zero period raises ValueError."""
        with pytest.raises(ValueError, match="'period' must be positive"):
            BollingerBandsStrategy({
                "period": 0,
                "num_std": 2.0,
            })

    def test_validate_params_negative_num_std(self):
        """Test that negative num_std raises ValueError."""
        with pytest.raises(ValueError, match="'num_std' must be positive"):
            BollingerBandsStrategy({
                "period": 20,
                "num_std": -2.0,
            })

    def test_validate_params_zero_num_std(self):
        """Test that zero num_std raises ValueError."""
        with pytest.raises(ValueError, match="'num_std' must be positive"):
            BollingerBandsStrategy({
                "period": 20,
                "num_std": 0.0,
            })


class TestBollingerBandsStrategyIndicators:
    """Test indicator calculation for Bollinger Bands Strategy."""

    def test_calculate_indicators_adds_bb_columns(self, sample_data):
        """Test that calculate_indicators adds Bollinger Bands columns."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        assert "bb_upper" in result.columns
        assert "bb_middle" in result.columns
        assert "bb_lower" in result.columns

    def test_calculate_indicators_preserves_original(self, sample_data):
        """Test that original OHLCV columns are preserved."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns
            pd.testing.assert_series_equal(result[col], sample_data[col])

    def test_calculate_indicators_band_relationship(self, sample_data):
        """Test that upper > middle > lower bands."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)

        # Remove NaN values for comparison
        valid_data = result.dropna()

        # Upper should be greater than middle
        assert (valid_data["bb_upper"] >= valid_data["bb_middle"]).all()

        # Middle should be greater than lower
        assert (valid_data["bb_middle"] >= valid_data["bb_lower"]).all()

    def test_calculate_indicators_middle_is_sma(self, sample_data):
        """Test that middle band equals SMA of close prices."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        result = strategy.calculate_indicators(sample_data)

        # Middle band should be close to rolling mean
        expected_middle = sample_data["close"].rolling(20).mean()

        # Compare non-NaN values
        valid_idx = ~result["bb_middle"].isna()
        pd.testing.assert_series_equal(
            result.loc[valid_idx, "bb_middle"],
            expected_middle.loc[valid_idx],
            check_names=False,
            atol=0.01,  # Small tolerance for floating point
        )


class TestBollingerBandsStrategySignals:
    """Test signal generation for Bollinger Bands Strategy."""

    def test_generate_signals_returns_series(self, sample_data):
        """Test that generate_signals returns a pandas Series."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)

    def test_generate_signals_range(self, sample_data):
        """Test that all signals are in valid range [-1.0, 1.0]."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        assert (signals >= -1.0).all()
        assert (signals <= 1.0).all()

    def test_generate_signals_only_valid_values(self, sample_data):
        """Test that signals only contain -1.0, 0.0, or 1.0."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        unique_signals = signals.unique()
        assert all(s in [-1.0, 0.0, 1.0] for s in unique_signals)

    def test_generate_signals_mostly_hold(self, sample_data):
        """Test that most signals are hold (0.0) for typical market data."""
        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 50,
        })
        signals = strategy.generate_signals(sample_data)
        # Most signals should be hold for normal market conditions
        hold_ratio = (signals == 0.0).sum() / len(signals)
        assert hold_ratio > 0.8  # At least 80% should be hold signals

    def test_different_num_std_different_signals(self, sample_data):
        """Test that different num_std values affect signal generation."""
        # Narrow bands (1 std)
        narrow = BollingerBandsStrategy({
            "period": 20,
            "num_std": 1.0,
            "min_required_rows": 50,
        })

        # Wide bands (3 std)
        wide = BollingerBandsStrategy({
            "period": 20,
            "num_std": 3.0,
            "min_required_rows": 50,
        })

        narrow_signals = narrow.generate_signals(sample_data)
        wide_signals = wide.generate_signals(sample_data)

        # Narrow bands should generate more signals (price crosses bands more often)
        narrow_count = (narrow_signals != 0.0).sum()
        wide_count = (wide_signals != 0.0).sum()

        assert narrow_count >= wide_count

    def test_generate_signals_detects_band_touches(self):
        """Test that strategy detects price touching bands."""
        # Create data where price clearly touches both bands
        dates = pd.date_range("2024-01-01", periods=60, freq="D")

        # Start stable, then spike up and down
        close_prices = np.concatenate([
            np.ones(25) * 100,         # Stable period
            np.linspace(100, 115, 10), # Sharp rise (touch upper band)
            np.linspace(115, 85, 10),  # Sharp fall (touch lower band)
            np.ones(15) * 100,         # Return to stable
        ])

        data = pd.DataFrame({
            "open": close_prices * 1.01,
            "high": close_prices * 1.02,
            "low": close_prices * 0.98,
            "close": close_prices,
            "volume": np.ones(60) * 1000000,
        }, index=dates)

        strategy = BollingerBandsStrategy({
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 25,
        })

        signals = strategy.generate_signals(data)

        # Should have at least some signals from band touches
        total_signals = (signals != 0.0).sum()
        assert total_signals > 0

    def test_custom_period(self, sample_data):
        """Test that custom period affects signal generation."""
        # Short period (10 days) - more responsive
        short_period = BollingerBandsStrategy({
            "period": 10,
            "num_std": 2.0,
            "min_required_rows": 15,
        })

        # Long period (30 days) - less responsive
        long_period = BollingerBandsStrategy({
            "period": 30,
            "num_std": 2.0,
            "min_required_rows": 35,
        })

        short_signals = short_period.generate_signals(sample_data)
        long_signals = long_period.generate_signals(sample_data)

        # Both should generate signals
        assert isinstance(short_signals, pd.Series)
        assert isinstance(long_signals, pd.Series)

        # Verify they're different strategies
        short_count = (short_signals != 0.0).sum()
        long_count = (long_signals != 0.0).sum()

        # At least one should generate signals
        assert short_count > 0 or long_count > 0
