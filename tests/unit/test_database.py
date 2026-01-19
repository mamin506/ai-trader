"""Unit tests for DatabaseManager."""

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.data.storage.database import DatabaseManager


class TestDatabaseManager:
    """Test cases for DatabaseManager."""

    @pytest.fixture
    def temp_db(self) -> str:
        """Create temporary database file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            return f.name

    @pytest.fixture
    def db_manager(self, temp_db: str) -> DatabaseManager:
        """Create DatabaseManager instance with temp DB."""
        return DatabaseManager(temp_db)

    @pytest.fixture
    def sample_bars(self) -> pd.DataFrame:
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

    def test_database_initialization(self, db_manager: DatabaseManager, temp_db: str) -> None:
        """Test database is initialized correctly."""
        assert Path(temp_db).exists()
        assert db_manager.db_path == temp_db

    def test_save_and_load_bars(
        self, db_manager: DatabaseManager, sample_bars: pd.DataFrame
    ) -> None:
        """Test saving and loading OHLCV bars."""
        # Save data
        db_manager.save_bars(sample_bars, "AAPL")

        # Load data back
        result = db_manager.load_bars(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        # Verify data structure
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert result.index.name == "date"

        # Verify data values (ignore freq attribute)
        pd.testing.assert_frame_equal(result, sample_bars, check_dtype=False, check_freq=False)

    def test_load_empty_symbol(self, db_manager: DatabaseManager) -> None:
        """Test loading non-existent symbol returns empty DataFrame."""
        result = db_manager.load_bars(
            "NONEXISTENT",
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_incremental_save(
        self, db_manager: DatabaseManager, sample_bars: pd.DataFrame
    ) -> None:
        """Test incremental data saving (UPSERT behavior)."""
        # Save first 3 days
        first_chunk = sample_bars.iloc[:3]
        db_manager.save_bars(first_chunk, "AAPL")

        # Save last 3 days (overlap with day 3)
        second_chunk = sample_bars.iloc[2:]
        db_manager.save_bars(second_chunk, "AAPL")

        # Load all data
        result = db_manager.load_bars(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

        # Should have all 5 days without duplicates
        assert len(result) == 5
        pd.testing.assert_frame_equal(result, sample_bars, check_dtype=False, check_freq=False)

    def test_date_range_filtering(
        self, db_manager: DatabaseManager, sample_bars: pd.DataFrame
    ) -> None:
        """Test loading with date range filtering."""
        # Save all data
        db_manager.save_bars(sample_bars, "AAPL")

        # Load subset
        result = db_manager.load_bars(
            "AAPL",
            datetime(2024, 1, 2),
            datetime(2024, 1, 4),
        )

        # Should return only 3 days
        assert len(result) == 3
        assert result.index[0] == pd.Timestamp("2024-01-02")
        assert result.index[-1] == pd.Timestamp("2024-01-04")

    def test_multiple_symbols(
        self, db_manager: DatabaseManager, sample_bars: pd.DataFrame
    ) -> None:
        """Test storing data for multiple symbols."""
        # Save same data for multiple symbols
        db_manager.save_bars(sample_bars, "AAPL")
        db_manager.save_bars(sample_bars, "GOOGL")

        # Load each separately
        aapl_data = db_manager.load_bars("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 5))
        googl_data = db_manager.load_bars("GOOGL", datetime(2024, 1, 1), datetime(2024, 1, 5))

        # Both should have data
        assert len(aapl_data) == 5
        assert len(googl_data) == 5

        # Verify they're independent
        pd.testing.assert_frame_equal(aapl_data, googl_data, check_dtype=False, check_freq=False)
