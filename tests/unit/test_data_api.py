"""Unit tests for DataAPI."""

import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.api.data_api import DataAPI


class TestDataAPI:
    """Test cases for DataAPI."""

    @pytest.fixture
    def temp_db(self) -> str:
        """Create temporary database file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            return f.name

    @pytest.fixture
    def api(self, temp_db: str) -> DataAPI:
        """Create DataAPI instance with temp DB."""
        return DataAPI(db_path=temp_db)

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
        assert api.db is not None

    def test_get_daily_bars_with_string_dates(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test get_daily_bars with string date arguments."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data

            result = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-05")

            # Verify provider was called
            mock_fetch.assert_called_once()
            args = mock_fetch.call_args[0]
            assert args[0] == "AAPL"
            assert isinstance(args[1], datetime)
            assert isinstance(args[2], datetime)
            assert args[1] == datetime(2024, 1, 1)
            assert args[2] == datetime(2024, 1, 5)

            # Verify result
            assert len(result) == 5
            assert list(result.columns) == ["open", "high", "low", "close", "volume"]

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
            assert len(result) == 5

    def test_get_daily_bars_caching(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test that get_daily_bars caches data in database."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data

            # First call - should fetch from provider
            result1 = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-05")
            assert mock_fetch.call_count == 1
            assert len(result1) == 5

            # Second call - should use cache (no additional provider call)
            result2 = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-05")
            assert mock_fetch.call_count == 1  # Still 1, not 2
            assert len(result2) == 5

            # Results should be identical
            pd.testing.assert_frame_equal(result1, result2, check_freq=False)

    def test_get_daily_bars_incremental_fetch(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test incremental fetching for missing data ranges."""
        # First fetch: Jan 1-3
        first_chunk = sample_data.iloc[:3]
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = first_chunk
            result1 = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-03")
            assert len(result1) == 3
            assert mock_fetch.call_count == 1

        # Second fetch: Jan 1-5 (should only fetch Jan 4-5)
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            # Return data for missing range
            missing_chunk = sample_data.iloc[3:]
            mock_fetch.return_value = missing_chunk

            result2 = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-05")

            # Should have fetched missing data
            assert mock_fetch.call_count == 1
            # Should have all 5 days now
            assert len(result2) == 5

    def test_get_latest_returns_recent_data(
        self, api: DataAPI, sample_data: pd.DataFrame
    ) -> None:
        """Test get_latest returns most recent N days."""
        from datetime import datetime
        from unittest.mock import patch as mock_patch

        # First populate the database with sample data
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.return_value = sample_data
            # Populate DB
            api.get_daily_bars("AAPL", "2024-01-01", "2024-01-05")

        # Mock datetime.now() to return a date close to our sample data
        fake_now = datetime(2024, 1, 5, 12, 0, 0)
        with mock_patch("src.api.data_api.datetime") as mock_datetime:
            mock_datetime.now.return_value = fake_now
            mock_datetime.fromisoformat = datetime.fromisoformat  # Keep real fromisoformat

            with patch.object(api.provider, "get_historical_bars") as mock_fetch:
                # Should not fetch since data is cached
                mock_fetch.return_value = pd.DataFrame()

                # Fetch latest 3 days
                result = api.get_latest("AAPL", days=3)

                # Should return the last 3 days from our 5-day dataset
                assert len(result) == 3

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
                assert len(df) == 5

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

    def test_info_handles_errors(self, api: DataAPI, capsys) -> None:
        """Test info handles errors gracefully."""
        with patch.object(api.provider, "get_historical_bars") as mock_fetch:
            mock_fetch.side_effect = Exception("API failed")

            api.info("INVALID")

            captured = capsys.readouterr()
            assert "Error fetching info" in captured.out
