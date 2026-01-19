"""Unit tests for MA Crossover Strategy."""

import numpy as np
import pandas as pd
import pytest

from src.strategy.ma_crossover import MACrossoverStrategy


class TestMACrossoverStrategy:
    """Test cases for MA Crossover Strategy."""

    @pytest.fixture
    def valid_params(self) -> dict:
        """Create valid strategy parameters."""
        return {"fast_period": 20, "slow_period": 50, "min_required_rows": 60}

    @pytest.fixture
    def uptrend_data(self) -> pd.DataFrame:
        """Create sample data with uptrend (for golden cross)."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        # Create uptrending price data
        close = 100 + np.arange(100) * 0.5  # Steady uptrend
        return pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": [1000000] * 100,
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    @pytest.fixture
    def downtrend_data(self) -> pd.DataFrame:
        """Create sample data with downtrend (for death cross)."""
        dates = pd.date_range(start="2024-01-01", periods=150, freq="D")
        # Create pattern: uptrend -> peak -> downtrend to trigger death cross
        close = np.concatenate([
            100 + np.arange(60) * 0.5,  # Uptrend (gets fast MA above slow MA)
            np.full(10, 130.0),  # Peak stabilization
            130 - np.arange(80) * 0.8  # Sharp downtrend (triggers death cross)
        ])
        return pd.DataFrame(
            {
                "open": close + 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": [1000000] * 150,
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    @pytest.fixture
    def crossover_data(self) -> pd.DataFrame:
        """Create data with clear MA crossover patterns."""
        dates = pd.date_range(start="2024-01-01", periods=150, freq="D")

        # Create price pattern with both crossovers:
        # uptrend -> peak -> downtrend -> trough -> uptrend
        close = np.concatenate(
            [
                100 + np.arange(40) * 0.6,  # Uptrend (golden cross setup)
                np.full(10, 124.0),  # Peak
                124 - np.arange(50) * 0.8,  # Downtrend (death cross)
                np.full(10, 84.0),  # Trough
                84 + np.arange(40) * 0.6,  # Uptrend (golden cross again)
            ]
        )

        return pd.DataFrame(
            {
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": [1000000] * 150,
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    def test_validate_params_success(self, valid_params: dict) -> None:
        """Test parameter validation succeeds with valid params."""
        strategy = MACrossoverStrategy(valid_params)
        assert strategy.params == valid_params

    def test_validate_params_missing_fast_period(self) -> None:
        """Test validation fails when fast_period is missing."""
        with pytest.raises(ValueError, match="'fast_period' parameter required"):
            MACrossoverStrategy({"slow_period": 50})

    def test_validate_params_missing_slow_period(self) -> None:
        """Test validation fails when slow_period is missing."""
        with pytest.raises(ValueError, match="'slow_period' parameter required"):
            MACrossoverStrategy({"fast_period": 20})

    def test_validate_params_negative_fast_period(self) -> None:
        """Test validation fails with negative fast_period."""
        with pytest.raises(ValueError, match="'fast_period' must be positive"):
            MACrossoverStrategy({"fast_period": -1, "slow_period": 50})

    def test_validate_params_zero_slow_period(self) -> None:
        """Test validation fails with zero slow_period."""
        with pytest.raises(ValueError, match="'slow_period' must be positive"):
            MACrossoverStrategy({"fast_period": 20, "slow_period": 0})

    def test_validate_params_fast_greater_than_slow(self) -> None:
        """Test validation fails when fast_period >= slow_period."""
        with pytest.raises(
            ValueError, match="'fast_period' must be less than 'slow_period'"
        ):
            MACrossoverStrategy({"fast_period": 50, "slow_period": 20})

    def test_validate_params_fast_equals_slow(self) -> None:
        """Test validation fails when fast_period == slow_period."""
        with pytest.raises(
            ValueError, match="'fast_period' must be less than 'slow_period'"
        ):
            MACrossoverStrategy({"fast_period": 50, "slow_period": 50})

    def test_calculate_indicators_adds_ma_columns(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test calculate_indicators adds fast_ma and slow_ma columns."""
        strategy = MACrossoverStrategy(valid_params)
        result = strategy.calculate_indicators(uptrend_data)

        assert "fast_ma" in result.columns
        assert "slow_ma" in result.columns
        assert len(result) == len(uptrend_data)

    def test_calculate_indicators_preserves_original(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test calculate_indicators doesn't modify original DataFrame."""
        strategy = MACrossoverStrategy(valid_params)
        original_columns = set(uptrend_data.columns)

        result = strategy.calculate_indicators(uptrend_data)

        # Original unchanged
        assert set(uptrend_data.columns) == original_columns
        # Result has new columns
        assert "fast_ma" in result.columns
        assert "slow_ma" in result.columns

    def test_calculate_indicators_ma_values(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test MA values are calculated correctly."""
        strategy = MACrossoverStrategy(valid_params)
        result = strategy.calculate_indicators(uptrend_data)

        # Fast MA should have NaN for first (fast_period - 1) rows
        assert result["fast_ma"].iloc[: valid_params["fast_period"] - 1].isna().all()
        # Slow MA should have NaN for first (slow_period - 1) rows
        assert result["slow_ma"].iloc[: valid_params["slow_period"] - 1].isna().all()

        # Later values should be valid
        assert not result["fast_ma"].iloc[valid_params["fast_period"] :].isna().all()
        assert not result["slow_ma"].iloc[valid_params["slow_period"] :].isna().all()

    def test_generate_signals_returns_series(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test generate_signals returns Series with correct structure."""
        strategy = MACrossoverStrategy(valid_params)
        signals = strategy.generate_signals(uptrend_data)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(uptrend_data)
        assert signals.name == "signal"
        pd.testing.assert_index_equal(signals.index, uptrend_data.index)

    def test_generate_signals_range(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test signals are in valid range [-1.0, 1.0]."""
        strategy = MACrossoverStrategy(valid_params)
        signals = strategy.generate_signals(uptrend_data)

        assert signals.min() >= -1.0
        assert signals.max() <= 1.0
        # Should only have values: -1.0, 0.0, or 1.0
        unique_values = signals.unique()
        assert all(val in [-1.0, 0.0, 1.0] for val in unique_values)

    def test_generate_signals_uptrend_golden_cross(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test uptrend data generates golden cross (buy signal)."""
        strategy = MACrossoverStrategy(valid_params)
        signals = strategy.generate_signals(uptrend_data)

        # In uptrend, should eventually get golden cross (buy signal)
        buy_signals = (signals == 1.0).sum()
        assert buy_signals > 0, "Uptrend should generate at least one buy signal"

    def test_generate_signals_downtrend_death_cross(
        self, valid_params: dict, downtrend_data: pd.DataFrame
    ) -> None:
        """Test downtrend data generates death cross (sell signal)."""
        strategy = MACrossoverStrategy(valid_params)
        signals = strategy.generate_signals(downtrend_data)

        # In downtrend, should eventually get death cross (sell signal)
        sell_signals = (signals == -1.0).sum()
        assert sell_signals > 0, "Downtrend should generate at least one sell signal"

    def test_generate_signals_mostly_hold(
        self, valid_params: dict, uptrend_data: pd.DataFrame
    ) -> None:
        """Test that most signals are hold (0.0) - crossovers are rare."""
        strategy = MACrossoverStrategy(valid_params)
        signals = strategy.generate_signals(uptrend_data)

        hold_signals = (signals == 0.0).sum()
        total_signals = len(signals)

        # Most signals should be hold (crossovers are infrequent events)
        assert hold_signals > total_signals * 0.8, "Most signals should be hold"

    def test_generate_signals_crossover_detection(
        self, crossover_data: pd.DataFrame
    ) -> None:
        """Test strategy detects both golden and death crosses."""
        strategy = MACrossoverStrategy({"fast_period": 10, "slow_period": 20})
        signals = strategy.generate_signals(crossover_data)

        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()

        # Should have at least one crossover in each direction
        assert buy_signals > 0, "Should detect golden cross"
        assert sell_signals > 0, "Should detect death cross"

    def test_generate_signals_no_duplicate_crossovers(
        self, valid_params: dict, crossover_data: pd.DataFrame
    ) -> None:
        """Test that consecutive signals of same type don't occur."""
        strategy = MACrossoverStrategy(valid_params)
        signals = strategy.generate_signals(crossover_data)

        # Get non-zero signals
        non_zero_signals = signals[signals != 0.0]

        # Check no consecutive duplicates
        if len(non_zero_signals) > 1:
            # Diff should never be 0 (would indicate consecutive same signals)
            consecutive_same = (non_zero_signals.diff() == 0).sum()
            assert (
                consecutive_same == 0
            ), "Should not have consecutive identical crossover signals"

    def test_different_periods_different_signals(
        self, uptrend_data: pd.DataFrame
    ) -> None:
        """Test different MA periods produce different signals."""
        strategy1 = MACrossoverStrategy({"fast_period": 10, "slow_period": 20})
        strategy2 = MACrossoverStrategy({"fast_period": 20, "slow_period": 50})

        signals1 = strategy1.generate_signals(uptrend_data)
        signals2 = strategy2.generate_signals(uptrend_data)

        # Signals should differ (different periods = different sensitivity)
        assert not signals1.equals(signals2)

    def test_strategy_with_minimal_data(self) -> None:
        """Test strategy with exactly minimum required data."""
        strategy = MACrossoverStrategy(
            {"fast_period": 5, "slow_period": 10, "min_required_rows": 15}
        )

        # Create minimal data (exactly min_required_rows)
        dates = pd.date_range(start="2024-01-01", periods=15, freq="D")
        data = pd.DataFrame(
            {
                "open": [100.0] * 15,
                "high": [105.0] * 15,
                "low": [95.0] * 15,
                "close": [100.0 + i for i in range(15)],
                "volume": [1000000] * 15,
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

        # Should validate successfully
        assert strategy.validate_data(data)

        # Should generate signals
        signals = strategy.generate_signals(data)
        assert len(signals) == 15
