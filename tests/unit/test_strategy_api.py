"""Unit tests for StrategyAPI."""

import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from src.api.data_api import DataAPI
from src.api.strategy_api import StrategyAPI
from src.strategy.ma_crossover import MACrossoverStrategy


class TestStrategyAPI:
    """Test cases for StrategyAPI."""

    @pytest.fixture
    def temp_db(self) -> str:
        """Create temporary database file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            return f.name

    @pytest.fixture
    def data_api(self, temp_db: str) -> DataAPI:
        """Create DataAPI instance with temp DB."""
        return DataAPI(db_path=temp_db)

    @pytest.fixture
    def strategy_api(self, data_api: DataAPI) -> StrategyAPI:
        """Create StrategyAPI instance."""
        return StrategyAPI(data_api=data_api)

    @pytest.fixture
    def strategy(self) -> MACrossoverStrategy:
        """Create MA Crossover strategy."""
        return MACrossoverStrategy({"fast_period": 5, "slow_period": 10, "min_required_rows": 20})

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample uptrend data."""
        dates = pd.date_range(start="2024-01-01", periods=60, freq="D")
        close = 100 + np.arange(60) * 0.5  # Uptrend
        return pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": [1000000] * 60,
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    def test_api_initialization_default(self) -> None:
        """Test StrategyAPI initializes with default DataAPI."""
        api = StrategyAPI()
        assert isinstance(api.data_api, DataAPI)

    def test_api_initialization_custom_data_api(self, data_api: DataAPI) -> None:
        """Test StrategyAPI initializes with custom DataAPI."""
        api = StrategyAPI(data_api=data_api)
        assert api.data_api is data_api

    def test_get_signals_returns_series(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test get_signals returns Series with correct structure."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            signals = strategy_api.get_signals("AAPL", strategy, "2024-01-01", "2024-03-01")

            assert isinstance(signals, pd.Series)
            assert len(signals) == len(sample_data)
            assert signals.name == "signal"

    def test_get_signals_range(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test signals are in valid range [-1.0, 1.0]."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            signals = strategy_api.get_signals("AAPL", strategy, "2024-01-01", "2024-03-01")

            assert signals.min() >= -1.0
            assert signals.max() <= 1.0

    def test_get_signals_with_empty_data(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy
    ) -> None:
        """Test get_signals handles empty data gracefully."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = pd.DataFrame()

            signals = strategy_api.get_signals("INVALID", strategy, "2024-01-01", "2024-03-01")

            assert isinstance(signals, pd.Series)
            assert signals.empty

    def test_get_signals_with_insufficient_data(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy
    ) -> None:
        """Test get_signals handles insufficient data (validation fails)."""
        # Create data with only 5 rows (less than strategy needs)
        short_data = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [105.0] * 5,
                "low": [95.0] * 5,
                "close": [100.0] * 5,
                "volume": [1000000] * 5,
            },
            index=pd.date_range(start="2024-01-01", periods=5, freq="D", name="date"),
        )

        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = short_data

            signals = strategy_api.get_signals("AAPL", strategy, "2024-01-01", "2024-01-05")

            # Should return empty series due to validation failure
            assert signals.empty

    def test_backtest_returns_dict(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test backtest returns dictionary with expected keys."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            results = strategy_api.backtest("AAPL", strategy, "2024-01-01", "2024-03-01")

            assert isinstance(results, dict)
            assert "total_return" in results
            assert "num_trades" in results
            assert "num_signals" in results
            assert "final_value" in results
            assert "buy_and_hold_return" in results

    def test_backtest_with_empty_data(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy
    ) -> None:
        """Test backtest handles empty data gracefully."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = pd.DataFrame()

            results = strategy_api.backtest("INVALID", strategy, "2024-01-01", "2024-03-01")

            assert results["total_return"] == 0.0
            assert results["num_trades"] == 0
            assert results["final_value"] == 10000.0  # Initial capital

    def test_backtest_uptrend_positive_return(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test backtest on uptrend data generates positive return."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            results = strategy_api.backtest("AAPL", strategy, "2024-01-01", "2024-03-01")

            # In uptrend, strategy should make money
            assert results["total_return"] > 0, "Uptrend should generate positive return"
            assert results["final_value"] > results["initial_capital"]

    def test_backtest_custom_initial_capital(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test backtest with custom initial capital."""
        custom_capital = 50000.0

        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            results = strategy_api.backtest(
                "AAPL", strategy, "2024-01-01", "2024-03-01", initial_capital=custom_capital
            )

            assert results["initial_capital"] == custom_capital
            # Final value should be different from default
            assert results["final_value"] != 10000.0

    def test_backtest_compares_to_buy_and_hold(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test backtest includes buy-and-hold benchmark."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            results = strategy_api.backtest("AAPL", strategy, "2024-01-01", "2024-03-01")

            # Buy-and-hold should also be positive in uptrend
            assert results["buy_and_hold_return"] > 0
            # Both returns should be reasonable percentages
            assert -1.0 < results["total_return"] < 5.0
            assert -1.0 < results["buy_and_hold_return"] < 5.0

    def test_backtest_counts_trades(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test backtest counts number of trades correctly."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            results = strategy_api.backtest("AAPL", strategy, "2024-01-01", "2024-03-01")

            # Should have at least one buy signal in uptrend
            assert results["num_buy_signals"] > 0
            # Trades should be counted
            assert results["num_trades"] >= 0

    def test_get_strategy_data_returns_dataframe(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test get_strategy_data returns DataFrame with indicators."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            data = strategy_api.get_strategy_data("AAPL", strategy, "2024-01-01", "2024-03-01")

            assert isinstance(data, pd.DataFrame)
            assert len(data) == len(sample_data)

    def test_get_strategy_data_includes_indicators(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test get_strategy_data includes calculated indicators."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            data = strategy_api.get_strategy_data("AAPL", strategy, "2024-01-01", "2024-03-01")

            # Should have original OHLCV columns
            assert "close" in data.columns
            assert "volume" in data.columns

            # Should have strategy-specific indicators (MA Crossover adds these)
            assert "fast_ma" in data.columns
            assert "slow_ma" in data.columns

            # Should have signals
            assert "signal" in data.columns

    def test_get_strategy_data_with_empty_data(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy
    ) -> None:
        """Test get_strategy_data handles empty data gracefully."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = pd.DataFrame()

            data = strategy_api.get_strategy_data("INVALID", strategy, "2024-01-01", "2024-03-01")

            assert isinstance(data, pd.DataFrame)
            assert data.empty

    def test_get_signals_with_datetime_objects(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test get_signals accepts datetime objects."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            start = datetime(2024, 1, 1)
            end = datetime(2024, 3, 1)

            signals = strategy_api.get_signals("AAPL", strategy, start, end)

            assert isinstance(signals, pd.Series)
            assert len(signals) > 0

    def test_backtest_with_datetime_objects(
        self, strategy_api: StrategyAPI, strategy: MACrossoverStrategy, sample_data: pd.DataFrame
    ) -> None:
        """Test backtest accepts datetime objects."""
        with patch.object(strategy_api.data_api, "get_daily_bars") as mock_bars:
            mock_bars.return_value = sample_data

            start = datetime(2024, 1, 1)
            end = datetime(2024, 3, 1)

            results = strategy_api.backtest("AAPL", strategy, start, end)

            assert isinstance(results, dict)
            assert results["num_signals"] > 0
