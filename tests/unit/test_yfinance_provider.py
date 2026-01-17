"""Unit tests for YFinanceProvider."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.providers.yfinance_provider import YFinanceProvider
from src.utils.exceptions import DataProviderError, DataQualityError


class TestYFinanceProvider:
    """Test cases for YFinanceProvider."""

    @pytest.fixture
    def provider(self) -> YFinanceProvider:
        """Create YFinanceProvider instance."""
        return YFinanceProvider()

    @pytest.fixture
    def sample_yfinance_data(self) -> pd.DataFrame:
        """Create sample data in yfinance format (capitalized columns)."""
        dates = pd.date_range(start="2024-01-01", end="2024-01-05", freq="D")
        return pd.DataFrame(
            {
                "Open": [150.0, 151.0, 152.0, 153.0, 154.0],
                "High": [155.0, 156.0, 157.0, 158.0, 159.0],
                "Low": [148.0, 149.0, 150.0, 151.0, 152.0],
                "Close": [152.0, 153.0, 154.0, 155.0, 156.0],
                "Volume": [1000000, 1100000, 1200000, 1300000, 1400000],
                "Dividends": [0, 0, 0, 0, 0],  # yfinance includes this
                "Stock Splits": [0, 0, 0, 0, 0],  # yfinance includes this
            },
            index=dates,
        )

    def test_get_historical_bars_success(
        self, provider: YFinanceProvider, sample_yfinance_data: pd.DataFrame
    ) -> None:
        """Test successful data fetching."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = sample_yfinance_data
            mock_ticker.return_value = mock_instance

            result = provider.get_historical_bars(
                "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
            )

            # Verify data structure
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 5
            assert list(result.columns) == ["open", "high", "low", "close", "volume"]
            assert result.index.name == "date"

    def test_column_name_standardization(
        self, provider: YFinanceProvider, sample_yfinance_data: pd.DataFrame
    ) -> None:
        """Test that yfinance capitalized columns are lowercased."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = sample_yfinance_data
            mock_ticker.return_value = mock_instance

            result = provider.get_historical_bars(
                "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
            )

            # All column names should be lowercase
            for col in result.columns:
                assert col.islower()

    def test_volume_is_integer(
        self, provider: YFinanceProvider, sample_yfinance_data: pd.DataFrame
    ) -> None:
        """Test that volume is converted to integer."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = sample_yfinance_data
            mock_ticker.return_value = mock_instance

            result = provider.get_historical_bars(
                "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
            )

            assert result["volume"].dtype in [int, "int64"]

    def test_only_required_columns_returned(
        self, provider: YFinanceProvider, sample_yfinance_data: pd.DataFrame
    ) -> None:
        """Test that only OHLCV columns are returned."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = sample_yfinance_data
            mock_ticker.return_value = mock_instance

            result = provider.get_historical_bars(
                "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
            )

            # Should not include Dividends or Stock Splits
            assert "Dividends" not in result.columns
            assert "Stock Splits" not in result.columns
            assert len(result.columns) == 5

    def test_empty_data_raises_data_quality_error(
        self, provider: YFinanceProvider
    ) -> None:
        """Test that empty data raises DataQualityError."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = pd.DataFrame()
            mock_ticker.return_value = mock_instance

            with pytest.raises(DataQualityError, match="No data returned"):
                provider.get_historical_bars(
                    "INVALID", datetime(2024, 1, 1), datetime(2024, 1, 5)
                )

    def test_none_data_raises_data_quality_error(
        self, provider: YFinanceProvider
    ) -> None:
        """Test that None data raises DataQualityError."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = None
            mock_ticker.return_value = mock_instance

            with pytest.raises(DataQualityError, match="No data returned"):
                provider.get_historical_bars(
                    "INVALID", datetime(2024, 1, 1), datetime(2024, 1, 5)
                )

    def test_api_exception_raises_data_provider_error(
        self, provider: YFinanceProvider
    ) -> None:
        """Test that API exceptions are wrapped in DataProviderError."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.side_effect = Exception("API connection failed")

            with pytest.raises(DataProviderError, match="Failed to fetch data"):
                provider.get_historical_bars(
                    "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
                )

    def test_correct_date_range(
        self, provider: YFinanceProvider, sample_yfinance_data: pd.DataFrame
    ) -> None:
        """Test that correct date range is returned."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = sample_yfinance_data
            mock_ticker.return_value = mock_instance

            result = provider.get_historical_bars(
                "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
            )

            # Check date range
            assert result.index[0] == pd.Timestamp("2024-01-01")
            assert result.index[-1] == pd.Timestamp("2024-01-05")

    def test_data_values_preserved(
        self, provider: YFinanceProvider, sample_yfinance_data: pd.DataFrame
    ) -> None:
        """Test that data values are correctly preserved after transformation."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value = sample_yfinance_data
            mock_ticker.return_value = mock_instance

            result = provider.get_historical_bars(
                "AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5)
            )

            # Check first row values
            assert result.iloc[0]["open"] == 150.0
            assert result.iloc[0]["high"] == 155.0
            assert result.iloc[0]["low"] == 148.0
            assert result.iloc[0]["close"] == 152.0
            assert result.iloc[0]["volume"] == 1000000

    def test_provider_is_instance_of_data_provider(
        self, provider: YFinanceProvider
    ) -> None:
        """Test that YFinanceProvider is instance of DataProvider."""
        from src.data.base import DataProvider

        assert isinstance(provider, DataProvider)
