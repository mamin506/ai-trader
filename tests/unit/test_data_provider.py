"""Unit tests for DataProvider interface."""

from datetime import datetime

import pandas as pd
import pytest

from src.data.base import DataProvider


class ConcreteDataProvider(DataProvider):
    """Concrete implementation for testing purposes."""

    def __init__(self, data: pd.DataFrame | None = None):
        """Initialize with optional test data.

        Args:
            data: DataFrame to return from get_historical_bars
        """
        self._data = data

    def get_historical_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Return test data."""
        if self._data is not None:
            return self._data

        # Return sample data
        dates = pd.date_range(start=start_date, end=end_date, freq="D")
        return pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [105.0] * len(dates),
                "low": [95.0] * len(dates),
                "close": [102.0] * len(dates),
                "volume": [1000000] * len(dates),
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )


class TestDataProviderInterface:
    """Test cases for DataProvider abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that DataProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DataProvider()  # type: ignore

    def test_concrete_implementation_required(self) -> None:
        """Test that subclass must implement get_historical_bars."""

        class IncompleteProvider(DataProvider):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()  # type: ignore

    def test_concrete_implementation_works(self) -> None:
        """Test that proper implementation can be instantiated."""
        provider = ConcreteDataProvider()
        assert isinstance(provider, DataProvider)

    def test_get_historical_bars_signature(self) -> None:
        """Test get_historical_bars returns DataFrame with correct structure."""
        provider = ConcreteDataProvider()
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)

        result = provider.get_historical_bars("AAPL", start, end)

        # Check it returns a DataFrame
        assert isinstance(result, pd.DataFrame)

        # Check required columns exist
        required_columns = ["open", "high", "low", "close", "volume"]
        for col in required_columns:
            assert col in result.columns, f"Missing column: {col}"

        # Check index is datetime
        assert isinstance(result.index, pd.DatetimeIndex)
        assert result.index.name == "date"

    def test_get_historical_bars_returns_correct_data(self) -> None:
        """Test get_historical_bars returns data for correct date range."""
        provider = ConcreteDataProvider()
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 3)

        result = provider.get_historical_bars("AAPL", start, end)

        # Check date range (should have 3 days: Jan 1, 2, 3)
        assert len(result) == 3
        assert result.index[0] == pd.Timestamp("2024-01-01")
        assert result.index[-1] == pd.Timestamp("2024-01-03")

    def test_get_historical_bars_data_types(self) -> None:
        """Test get_historical_bars returns correct data types."""
        provider = ConcreteDataProvider()
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 1)

        result = provider.get_historical_bars("AAPL", start, end)

        # Check data types
        assert result["open"].dtype in [float, "float64"]
        assert result["high"].dtype in [float, "float64"]
        assert result["low"].dtype in [float, "float64"]
        assert result["close"].dtype in [float, "float64"]
        assert result["volume"].dtype in [int, "int64"]

    def test_custom_data_provider(self) -> None:
        """Test custom data can be injected for testing."""
        custom_data = pd.DataFrame(
            {
                "open": [150.0, 151.0],
                "high": [155.0, 156.0],
                "low": [148.0, 149.0],
                "close": [152.0, 153.0],
                "volume": [2000000, 2100000],
            },
            index=pd.DatetimeIndex(
                [datetime(2024, 1, 1), datetime(2024, 1, 2)], name="date"
            ),
        )

        provider = ConcreteDataProvider(data=custom_data)
        result = provider.get_historical_bars("TEST", datetime.now(), datetime.now())

        # Should return our custom data
        pd.testing.assert_frame_equal(result, custom_data)

    def test_provider_interface_with_different_symbols(self) -> None:
        """Test provider can handle different symbols."""
        provider = ConcreteDataProvider()

        symbols = ["AAPL", "TSLA", "GOOGL"]
        for symbol in symbols:
            result = provider.get_historical_bars(
                symbol, datetime(2024, 1, 1), datetime(2024, 1, 1)
            )
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
