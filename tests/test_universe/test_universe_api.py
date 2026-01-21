"""Tests for Universe API."""

import pytest
import pandas as pd
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.api.universe_api import UniverseAPI


@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path."""
    return str(tmp_path / "test_universe.db")


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary cache directory."""
    return tmp_path / "universe_cache"


@pytest.fixture
def mock_selector():
    """Mock StaticUniverseSelector."""
    with patch("src.api.universe_api.StaticUniverseSelector") as mock:
        selector_instance = MagicMock()
        selector_instance.select.return_value = ["AAPL", "MSFT", "GOOGL"]

        # Return proper DataFrame for metadata
        metadata_df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "GOOGL"],
            "rank": [1, 2, 3],
            "price": [150.0, 300.0, 100.0],
        })
        selector_instance.get_universe_metadata.return_value = metadata_df

        mock.return_value = selector_instance
        yield mock


def test_api_initialization(temp_db_path, temp_cache_dir):
    """Test API initialization."""
    api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)

    assert api.db is not None
    assert api.cache_dir == temp_cache_dir
    assert temp_cache_dir.exists()


def test_select_universe(temp_db_path, temp_cache_dir, mock_selector):
    """Test universe selection."""
    api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)

    symbols = api.select_universe(
        name="test_universe",
        top_n=50,
        min_price=10.0,
        min_avg_volume=1_000_000,
        save=False,
    )

    assert len(symbols) == 3
    assert "AAPL" in symbols


def test_select_universe_with_save(temp_db_path, temp_cache_dir, mock_selector):
    """Test universe selection with database save."""
    api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)

    symbols = api.select_universe(
        name="test_universe",
        top_n=50,
        save=True,
    )

    # Verify it was saved
    loaded_symbols = api.load_universe("test_universe")
    assert loaded_symbols == symbols


def test_load_universe_not_found(temp_db_path, temp_cache_dir):
    """Test loading non-existent universe."""
    api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)

    with pytest.raises(ValueError, match="No universe found"):
        api.load_universe("nonexistent")


def test_get_universe_dates(temp_db_path, temp_cache_dir, mock_selector):
    """Test retrieving universe dates."""
    api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)

    # Create universes on different dates
    date1 = datetime(2024, 1, 1)
    date2 = datetime(2024, 2, 1)

    api.select_universe(name="test", date=date1, save=True)
    api.select_universe(name="test", date=date2, save=True)

    dates = api.get_universe_dates("test")

    assert len(dates) == 2
    assert "2024-02-01" in dates
    assert "2024-01-01" in dates


def test_select_universe_with_date_string(temp_db_path, temp_cache_dir, mock_selector):
    """Test universe selection with date as string."""
    api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)

    symbols = api.select_universe(
        name="test",
        date="2024-01-15",
        save=True,
    )

    # Load with date string
    loaded = api.load_universe("test", date="2024-01-15")
    assert loaded == symbols


def test_refresh_listings_cache(temp_db_path, temp_cache_dir):
    """Test refreshing listings cache."""
    with patch("src.universe.providers.alphavantage.AlphaVantageProvider") as mock_provider_class:
        mock_provider = MagicMock()
        mock_provider.fetch_listings.return_value = MagicMock(
            __len__=lambda self: 1000
        )
        mock_provider_class.return_value = mock_provider

        api = UniverseAPI(db_path=temp_db_path, cache_dir=temp_cache_dir)
        count = api.refresh_listings_cache()

        assert count == 1000
        mock_provider.fetch_listings.assert_called_once_with(use_cache=False)
