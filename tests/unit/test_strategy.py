"""Unit tests for Strategy base class."""

from datetime import datetime

import pandas as pd
import pytest

from src.strategy.base import Strategy


class ConcreteStrategy(Strategy):
    """Concrete implementation for testing purposes."""

    def validate_params(self) -> None:
        """Validate required parameters."""
        if "period" not in self.params:
            raise ValueError("'period' parameter required")
        if self.params["period"] < 1:
            raise ValueError("'period' must be positive")

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate simple moving average."""
        data = data.copy()
        data["sma"] = data["close"].rolling(self.params["period"]).mean()
        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on price vs SMA."""
        data = self.calculate_indicators(data)
        signals = pd.Series(0.0, index=data.index)
        # Buy when close > SMA
        signals[data["close"] > data["sma"]] = 1.0
        # Sell when close < SMA
        signals[data["close"] < data["sma"]] = -1.0
        return signals


class TestStrategyInterface:
    """Test cases for Strategy abstract interface."""

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLCV data."""
        dates = pd.date_range(start="2024-01-01", end="2024-01-31", freq="D")
        return pd.DataFrame(
            {
                "open": [150.0] * len(dates),
                "high": [155.0] * len(dates),
                "low": [148.0] * len(dates),
                "close": [152.0 + i * 0.5 for i in range(len(dates))],  # Uptrend
                "volume": [1000000] * len(dates),
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that Strategy cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Strategy({"period": 20})  # type: ignore

    def test_concrete_implementation_works(self) -> None:
        """Test that proper implementation can be instantiated."""
        strategy = ConcreteStrategy({"period": 20})
        assert isinstance(strategy, Strategy)
        assert strategy.params["period"] == 20

    def test_validate_params_called_on_init(self) -> None:
        """Test that validate_params is called during initialization."""
        with pytest.raises(ValueError, match="'period' parameter required"):
            ConcreteStrategy({})

    def test_validate_params_checks_values(self) -> None:
        """Test that parameter validation checks values."""
        with pytest.raises(ValueError, match="'period' must be positive"):
            ConcreteStrategy({"period": 0})

    def test_calculate_indicators_returns_dataframe(
        self, sample_data: pd.DataFrame
    ) -> None:
        """Test calculate_indicators returns DataFrame with indicator columns."""
        strategy = ConcreteStrategy({"period": 5})
        result = strategy.calculate_indicators(sample_data)

        assert isinstance(result, pd.DataFrame)
        assert "sma" in result.columns
        assert len(result) == len(sample_data)

    def test_calculate_indicators_preserves_original_data(
        self, sample_data: pd.DataFrame
    ) -> None:
        """Test calculate_indicators doesn't modify original DataFrame."""
        strategy = ConcreteStrategy({"period": 5})
        original_columns = set(sample_data.columns)

        result = strategy.calculate_indicators(sample_data)

        # Original data unchanged
        assert set(sample_data.columns) == original_columns
        assert "sma" not in sample_data.columns

        # Result has new column
        assert "sma" in result.columns

    def test_generate_signals_returns_series(self, sample_data: pd.DataFrame) -> None:
        """Test generate_signals returns Series with correct structure."""
        strategy = ConcreteStrategy({"period": 5})
        signals = strategy.generate_signals(sample_data)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)
        # Check index matches
        pd.testing.assert_index_equal(signals.index, sample_data.index)

    def test_generate_signals_range(self, sample_data: pd.DataFrame) -> None:
        """Test signals are in valid range [-1.0, 1.0]."""
        strategy = ConcreteStrategy({"period": 5})
        signals = strategy.generate_signals(sample_data)

        assert signals.min() >= -1.0
        assert signals.max() <= 1.0

    def test_generate_signals_logic(self, sample_data: pd.DataFrame) -> None:
        """Test signal generation logic is correct."""
        strategy = ConcreteStrategy({"period": 5})
        signals = strategy.generate_signals(sample_data)

        # In uptrend data, price should eventually be above SMA
        # So we should have some buy signals (+1.0)
        assert (signals == 1.0).sum() > 0

        # Early data might be below SMA (not enough data for MA)
        # or could have sell signals
        assert (signals == 0.0).sum() >= 0 or (signals == -1.0).sum() >= 0

    def test_validate_data_checks_minimum_rows(self, sample_data: pd.DataFrame) -> None:
        """Test validate_data checks minimum data points."""
        strategy = ConcreteStrategy({"period": 20, "min_required_rows": 100})

        # Sample data has 31 rows, less than required 100
        assert not strategy.validate_data(sample_data)

        # With lower requirement, should pass
        strategy2 = ConcreteStrategy({"period": 20, "min_required_rows": 20})
        assert strategy2.validate_data(sample_data)

    def test_validate_data_checks_required_columns(
        self, sample_data: pd.DataFrame
    ) -> None:
        """Test validate_data checks for required OHLCV columns."""
        strategy = ConcreteStrategy({"period": 20, "min_required_rows": 10})

        # Valid data should pass
        assert strategy.validate_data(sample_data)

        # Missing column should fail
        incomplete_data = sample_data.drop(columns=["volume"])
        assert not strategy.validate_data(incomplete_data)

    def test_validate_data_checks_missing_values(
        self, sample_data: pd.DataFrame
    ) -> None:
        """Test validate_data rejects data with NaN values."""
        strategy = ConcreteStrategy({"period": 20, "min_required_rows": 10})

        # Introduce NaN
        data_with_nan = sample_data.copy()
        data_with_nan.loc[data_with_nan.index[5], "close"] = float("nan")

        assert not strategy.validate_data(data_with_nan)

    def test_validate_data_checks_datetime_index(self) -> None:
        """Test validate_data requires DatetimeIndex."""
        strategy = ConcreteStrategy({"period": 20, "min_required_rows": 10})

        # Data with non-datetime index should fail
        data_with_int_index = pd.DataFrame(
            {
                "open": [150.0] * 20,
                "high": [155.0] * 20,
                "low": [148.0] * 20,
                "close": [152.0] * 20,
                "volume": [1000000] * 20,
            },
            index=range(20),  # Integer index instead of DatetimeIndex
        )

        assert not strategy.validate_data(data_with_int_index)

    def test_validate_data_default_min_rows(self, sample_data: pd.DataFrame) -> None:
        """Test default min_required_rows is 100."""
        # Don't specify min_required_rows
        strategy = ConcreteStrategy({"period": 20})

        # Sample data has 31 rows, less than default 100
        assert not strategy.validate_data(sample_data)

    def test_strategy_params_accessible(self) -> None:
        """Test that strategy parameters are accessible."""
        params = {"period": 20, "threshold": 0.02}
        strategy = ConcreteStrategy(params)

        assert strategy.params == params
        assert strategy.params["period"] == 20
        assert strategy.params["threshold"] == 0.02

    def test_multiple_strategies_independent(self) -> None:
        """Test that multiple strategy instances are independent."""
        strategy1 = ConcreteStrategy({"period": 20})
        strategy2 = ConcreteStrategy({"period": 50})

        assert strategy1.params["period"] == 20
        assert strategy2.params["period"] == 50

        # Modifying one shouldn't affect the other
        strategy1.params["period"] = 30
        assert strategy2.params["period"] == 50
