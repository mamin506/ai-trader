"""Unit tests for DataAPI."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.api.data_api import DataAPI


class TestDataAPI:
    """Test cases for DataAPI."""

    @pytest.fixture
    def api(self) -> DataAPI:
        """Create DataAPI instance."""
        return DataAPI()

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLCV data."""
        dates = pd.date_range(start="2024-01-01", end="2024-01-05", freq="D")
        return pd.DataFrame(
            {
                "open": [150.0, 151.0, 152.0, 153.0, 154.0],
                "high": [155.0, 156.0, 157.0, 158.0, 159.0],
                "low": [148.0, 149.0, 150.0, 151.0, 152.0],
                "close": [152.0, 153.0, 154.0, 155.0, 156.0],
                "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

    def test_api_initialization(self, api: DataAPI) -> None:
        """Test DataAPI initializes with YFinanceProvider."""
        from src.data.providers.yfinance_provider import YFinanceProvider

        assert isinstance(api.provider, YFinanceProvider)

    def test_get_daily_bars_with_string_dates(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test get_daily_bars with string date arguments."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data

            result = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-05")

            # Verify provider was called with datetime objects
            mock_fetch.assert_called_once()
            args = mock_fetch.call_args[0]
            assert args[0] == "AAPL"
            assert isinstance(args[1], datetime)
            assert isinstance(args[2], datetime)
            assert args[1] == datetime(2024, 1, 1)
            assert args[2] == datetime(2024, 1, 5)

            # Verify result
            pd.testing.assert_frame_equal(result, sample_data)

    def test_get_daily_bars_with_datetime_objects(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test get_daily_bars with datetime objects."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data

            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 5)
            result = api.get_daily_bars("AAPL", start, end)

            mock_fetch.assert_called_once_with("AAPL", start, end)
            pd.testing.assert_frame_equal(result, sample_data)

    def test_get_latest_returns_recent_data(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test get_latest returns most recent N days."""
        # Create 60 days of data
        dates = pd.date_range(start="2024-01-01", end="2024-03-01", freq="D")
        large_data = pd.DataFrame(
            {
                "open": [150.0] * len(dates),
                "high": [155.0] * len(dates),
                "low": [148.0] * len(dates),
                "close": [152.0] * len(dates),
                "volume": [1000000] * len(dates),
            },
            index=pd.DatetimeIndex(dates, name="date"),
        )

        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = large_data

            result = api.get_latest("AAPL", days=30)

            # Should return only 30 days
            assert len(result) == 30

            # Should be the most recent 30 days
            assert result.index[-1] == large_data.index[-1]

    def test_get_multiple_symbols(self, api: DataAPI, sample_data: pd.DataFrame) -> None:
        """Test fetching data for multiple symbols."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data

            symbols = ["AAPL", "GOOGL", "MSFT"]
            result = api.get_multiple_symbols(symbols, "2024-01-01", "2024-01-05")

            # Should call provider for each symbol
            assert mock_fetch.call_count == 3

            # Should return dict with all symbols
            assert set(result.keys()) == set(symbols)

            # Each value should be a DataFrame
            for symbol, df in result.items():
                assert isinstance(df, pd.DataFrame)
                pd.testing.assert_frame_equal(df, sample_data)

    def test_get_multiple_symbols_handles_failures(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test get_multiple_symbols continues when one symbol fails."""
        def mock_fetch(symbol, start, end):
            if symbol == "INVALID":
                raise Exception("Failed to fetch")
            return sample_data

        with patch.object(api.provider, "get_historical_bars") as mock_fetch_method:
            mock_fetch_method.side_effect = mock_fetch

            symbols = ["AAPL", "INVALID", "GOOGL"]
            result = api.get_multiple_symbols(symbols, "2024-01-01", "2024-01-05")

            # Should return data for successful symbols
            assert "AAPL" in result
            assert "GOOGL" in result
            assert "INVALID" not in result

    def test_info_prints_summary(
        self, api: DataAPI, sample_data: pd.DataFrame, capsys
    ) -> None:
        """Test info prints summary information."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data

            api.info("AAPL")

            # Capture printed output
            captured = capsys.readouterr()

            # Verify key information is printed
            assert "AAPL" in captured.out
            assert "Symbol:" in captured.out
            assert "Latest close:" in captured.out
            assert "30-day high:" in captured.out
            assert "30-day low:" in captured.out

    def test_info_handles_errors(self, api: DataAPI, capsys) -> None:
        """Test info handles errors gracefully."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.side_effect = Exception("API failed")

            api.info("INVALID")

            captured = capsys.readouterr()
            assert "Error fetching info" in captured.out
