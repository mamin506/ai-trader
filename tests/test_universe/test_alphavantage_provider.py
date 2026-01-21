"""Tests for AlphaVantage provider."""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests

from src.universe.providers.alphavantage import AlphaVantageProvider
from src.utils.exceptions import DataProviderError


@pytest.fixture
def mock_alphavantage_response():
    """Mock CSV response from AlphaVantage."""
    csv_data = """symbol,name,exchange,assetType,ipoDate,delistingDate,status
AAPL,Apple Inc,NASDAQ,Stock,1980-12-12,,Active
MSFT,Microsoft Corporation,NASDAQ,Stock,1986-03-13,,Active
SPY,SPDR S&P 500 ETF Trust,NYSE ARCA,ETF,1993-01-22,,Active
DELISTED,Delisted Company,NASDAQ,Stock,2000-01-01,2020-01-01,Delisted
"""
    return csv_data


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary cache directory."""
    return tmp_path / "cache"


def test_provider_initialization(temp_cache_dir):
    """Test provider initialization."""
    provider = AlphaVantageProvider(cache_dir=temp_cache_dir)

    assert provider.api_key == "demo"
    assert provider.cache_dir == temp_cache_dir
    assert temp_cache_dir.exists()


def test_fetch_listings_success(mock_alphavantage_response, temp_cache_dir):
    """Test successful fetching of listings."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_alphavantage_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)
        df = provider.fetch_listings(use_cache=False)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 4
        assert "symbol" in df.columns
        assert "exchange" in df.columns
        assert "assetType" in df.columns


def test_fetch_listings_with_cache(mock_alphavantage_response, temp_cache_dir):
    """Test caching functionality."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_alphavantage_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)

        # First call - should hit API
        df1 = provider.fetch_listings(use_cache=True)
        assert mock_get.call_count == 1

        # Second call - should use cache
        df2 = provider.fetch_listings(use_cache=True)
        assert mock_get.call_count == 1  # No additional call

        # Verify data is same
        pd.testing.assert_frame_equal(df1, df2)


def test_fetch_listings_api_error(temp_cache_dir):
    """Test handling of API errors."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("API error")

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)

        with pytest.raises(DataProviderError, match="Failed to fetch listings"):
            provider.fetch_listings(use_cache=False)


def test_get_active_stocks(mock_alphavantage_response, temp_cache_dir):
    """Test filtering for active stocks only."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_alphavantage_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)
        df = provider.get_active_stocks()

        # Should only include AAPL and MSFT (not SPY which is ETF, not DELISTED)
        assert len(df) == 2
        assert "AAPL" in df["symbol"].values
        assert "MSFT" in df["symbol"].values
        assert "SPY" not in df["symbol"].values
        assert "DELISTED" not in df["symbol"].values


def test_get_active_stocks_exchange_filter(mock_alphavantage_response, temp_cache_dir):
    """Test filtering by exchange."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_alphavantage_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)
        df = provider.get_active_stocks(exchanges=["NASDAQ"])

        # Should only include NASDAQ stocks (AAPL, MSFT)
        assert len(df) == 2
        assert all(df["exchange"] == "NASDAQ")


def test_get_active_etfs(mock_alphavantage_response, temp_cache_dir):
    """Test filtering for active ETFs only."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_alphavantage_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)
        df = provider.get_active_etfs()

        # Should only include SPY
        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "SPY"


def test_cache_expiration(mock_alphavantage_response, temp_cache_dir):
    """Test force refresh bypasses cache."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_alphavantage_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(cache_dir=temp_cache_dir)

        # First call with cache
        provider.fetch_listings(use_cache=True)
        assert mock_get.call_count == 1

        # Second call with use_cache=False forces refetch
        provider.fetch_listings(use_cache=False)
        assert mock_get.call_count == 2  # Forced refresh
