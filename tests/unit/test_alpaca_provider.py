"""Unit tests for AlpacaProvider.

Tests the Alpaca data provider with mocked API responses.
"""

from datetime import datetime
from unittest.mock import Mock, MagicMock

import pandas as pd
import pytest

from src.data.providers.alpaca_provider import AlpacaProvider
from src.utils.exceptions import DataProviderError, DataQualityError


@pytest.fixture
def mock_alpaca_client():
    """Create a mock AlpacaClient."""
    client = Mock()
    client.with_retry = Mock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    return client


@pytest.fixture
def mock_data_client():
    """Create a mock StockHistoricalDataClient."""
    return Mock()


@pytest.fixture
def alpaca_provider(mock_alpaca_client, mock_data_client):
    """Create AlpacaProvider with mocked client."""
    mock_alpaca_client.get_data_client.return_value = mock_data_client
    return AlpacaProvider(mock_alpaca_client)


class TestAlpacaProviderInit:
    """Test AlpacaProvider initialization."""

    def test_init(self, mock_alpaca_client, mock_data_client):
        """Test provider initialization."""
        mock_alpaca_client.get_data_client.return_value = mock_data_client
        provider = AlpacaProvider(mock_alpaca_client)

        assert provider.client == mock_alpaca_client
        assert provider.data_client == mock_data_client
        mock_alpaca_client.get_data_client.assert_called_once()


class TestAlpacaProviderHistoricalBars:
    """Test get_historical_bars method."""

    def test_get_historical_bars_success(self, alpaca_provider, mock_data_client):
        """Test successful fetching of historical bars."""
        # Create mock bars response
        mock_bars_data = pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [104.0, 105.0, 106.0],
            "volume": [1000000, 1100000, 1200000],
            "trade_count": [5000, 5500, 6000],
            "vwap": [102.0, 103.0, 104.0],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-01-02", tz="UTC"),
            pd.Timestamp("2024-01-03", tz="UTC"),
        ]))
        mock_bars_data.index.name = "timestamp"

        # Mock the bars object
        mock_bars = Mock()
        mock_symbol_bars = Mock()
        mock_symbol_bars.df = mock_bars_data
        mock_symbol_bars.__len__ = Mock(return_value=3)  # Add len() support
        mock_bars.__getitem__ = Mock(return_value=mock_symbol_bars)
        mock_bars.__contains__ = Mock(return_value=True)

        mock_data_client.get_stock_bars.return_value = mock_bars

        # Test
        result = alpaca_provider.get_historical_bars(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 1, 3),
        )

        # Verify result
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert result.index.name == "date"
        assert result.index.tz is None  # Timezone should be removed
        assert result["volume"].dtype == int

    def test_get_historical_bars_no_data(self, alpaca_provider, mock_data_client):
        """Test when no data is returned."""
        mock_bars = Mock()
        mock_bars.__contains__ = Mock(return_value=False)
        mock_data_client.get_stock_bars.return_value = mock_bars

        with pytest.raises(DataQualityError, match="No data returned"):
            alpaca_provider.get_historical_bars(
                "INVALID",
                datetime(2024, 1, 1),
                datetime(2024, 1, 3),
            )

    def test_get_historical_bars_empty_dataframe(self, alpaca_provider, mock_data_client):
        """Test when empty DataFrame is returned."""
        mock_bars_data = pd.DataFrame()

        mock_bars = Mock()
        mock_symbol_bars = Mock()
        mock_symbol_bars.df = mock_bars_data
        mock_symbol_bars.__len__ = Mock(return_value=0)
        mock_bars.__getitem__ = Mock(return_value=mock_symbol_bars)
        mock_bars.__contains__ = Mock(return_value=True)

        mock_data_client.get_stock_bars.return_value = mock_bars

        with pytest.raises(DataQualityError, match="No bars returned"):
            alpaca_provider.get_historical_bars(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 3),
            )

    def test_get_historical_bars_missing_columns(self, alpaca_provider, mock_data_client):
        """Test when required columns are missing."""
        # Missing 'close' column
        mock_bars_data = pd.DataFrame({
            "open": [100.0],
            "high": [105.0],
            "low": [99.0],
            "volume": [1000000],
        }, index=pd.DatetimeIndex([pd.Timestamp("2024-01-01")]))

        mock_bars = Mock()
        mock_symbol_bars = Mock()
        mock_symbol_bars.df = mock_bars_data
        mock_symbol_bars.__len__ = Mock(return_value=1)  # Add len() support
        mock_bars.__getitem__ = Mock(return_value=mock_symbol_bars)
        mock_bars.__contains__ = Mock(return_value=True)

        mock_data_client.get_stock_bars.return_value = mock_bars

        with pytest.raises(DataQualityError, match="Missing required columns"):
            alpaca_provider.get_historical_bars(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 3),
            )

    def test_get_historical_bars_api_error(self, alpaca_provider, mock_data_client):
        """Test handling of API errors."""
        mock_data_client.get_stock_bars.side_effect = Exception("API Error")

        with pytest.raises(DataProviderError, match="Failed to fetch Alpaca data"):
            alpaca_provider.get_historical_bars(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 3),
            )


class TestAlpacaProviderLatestQuote:
    """Test get_latest_quote method."""

    def test_get_latest_quote_success(self, alpaca_provider, mock_data_client):
        """Test successful fetching of latest quote."""
        # Mock quote object
        mock_quote = Mock()
        mock_quote.bid_price = 100.50
        mock_quote.ask_price = 100.60
        mock_quote.timestamp = pd.Timestamp("2024-01-01 15:30:00", tz="UTC")

        # Mock quotes response
        mock_quotes = {
            "AAPL": mock_quote
        }
        mock_data_client.get_stock_latest_quote.return_value = mock_quotes

        # Test
        result = alpaca_provider.get_latest_quote("AAPL")

        # Verify result
        assert result["symbol"] == "AAPL"
        assert result["bid"] == 100.50
        assert result["ask"] == 100.60
        assert result["last"] == 100.55  # Midpoint
        assert isinstance(result["timestamp"], datetime)
        assert result["timestamp"].tzinfo is None  # Timezone removed

    def test_get_latest_quote_symbol_not_found(self, alpaca_provider, mock_data_client):
        """Test when symbol is not in quotes response."""
        mock_quotes = {}
        mock_data_client.get_stock_latest_quote.return_value = mock_quotes

        with pytest.raises(DataProviderError, match="No quote returned"):
            alpaca_provider.get_latest_quote("INVALID")

    def test_get_latest_quote_api_error(self, alpaca_provider, mock_data_client):
        """Test handling of API errors."""
        mock_data_client.get_stock_latest_quote.side_effect = Exception("API Error")

        with pytest.raises(DataProviderError, match="Failed to fetch latest quote"):
            alpaca_provider.get_latest_quote("AAPL")


class TestAlpacaProviderTradingDays:
    """Test get_trading_days method."""

    def test_get_trading_days_success(self, alpaca_provider):
        """Test successful fetching of trading days."""
        result = alpaca_provider.get_trading_days(
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        # Verify result
        assert isinstance(result, pd.DatetimeIndex)
        # Jan 1, 2024 is Monday (New Year's Day - holiday)
        # Jan 2 is Tuesday (first trading day of 2024)
        assert len(result) >= 3  # Should have at least 3 trading days

    def test_get_trading_days_week(self, alpaca_provider):
        """Test trading days for a full week."""
        # Week of Jan 8-12, 2024 (no holidays)
        result = alpaca_provider.get_trading_days(
            datetime(2024, 1, 8),
            datetime(2024, 1, 12),
        )

        # Should have 5 trading days (Mon-Fri)
        assert len(result) == 5
        assert result[0].tzinfo is None  # Naive datetime

    def test_get_trading_days_weekend(self, alpaca_provider):
        """Test that weekends are excluded."""
        # Weekend Jan 6-7, 2024 (Sat-Sun)
        result = alpaca_provider.get_trading_days(
            datetime(2024, 1, 6),
            datetime(2024, 1, 7),
        )

        # Should have 0 trading days
        assert len(result) == 0
