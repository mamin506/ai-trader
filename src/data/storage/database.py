"""SQLite database manager implementation.

This module provides the DatabaseManager class for handling all interactions
with the SQLite database, including connection management, table creation,
and data persistence.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import threading

import pandas as pd

from src.utils.logging import get_logger
from src.utils.exceptions import DataError

logger = get_logger(__name__)


class DatabaseManager:
    """Manages SQLite database interactions.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str):
        """Initialize database manager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.create_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            # Enable row factory for name-based access if needed,
            # though we mostly use pandas read_sql
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def create_tables(self) -> None:
        """Create necessary database tables if they don't exist."""
        schema_path = Path(__file__).parent / "schema.sql"
        try:
            with open(schema_path, "r") as f:
                schema = f.read()

            conn = self._get_connection()
            conn.executescript(schema)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise DataError(f"Database initialization failed: {e}") from e

    def save_bars(self, df: pd.DataFrame, symbol: str) -> None:
        """Save historical bars to database.

        Upserts data (replaces existing records for the same symbol/date).

        Args:
            df: DataFrame with datetime index "date" and OHLCV columns.
            symbol: Ticker symbol.
        """
        if df.empty:
            logger.warning(f"Attempted to save empty DataFrame for {symbol}")
            return

        # Prepare DataFrame for insertion
        data = df.copy()
        data["symbol"] = symbol
        data["updated_at"] = datetime.utcnow().isoformat()

        # Ensure index is in specific column for to_sql
        if data.index.name == "date":
            data = data.reset_index()

        # Convert Timestamp to string ISO format if not already
        if pd.api.types.is_datetime64_any_dtype(data["date"]):
            data["date"] = data["date"].dt.strftime("%Y-%m-%d")

        records = data.to_dict("records")

        insert_sql = """
            INSERT INTO market_data
            (symbol, date, open, high, low, close, volume, updated_at)
            VALUES (:symbol, :date, :open, :high, :low, :close, :volume, :updated_at)
            ON CONFLICT(symbol, date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            updated_at=excluded.updated_at
        """

        conn = self._get_connection()
        try:
            with conn:
                conn.executemany(insert_sql, records)
            logger.info(f"Saved {len(records)} bars for {symbol}")
        except Exception as e:
            logger.error(f"Failed to save bars for {symbol}: {e}")
            raise DataError(f"Failed to save data: {e}") from e

    def load_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Load historical bars from database.

        Args:
            symbol: Ticker symbol.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            DataFrame with OHLCV data and datetime index "date".
        """
        query = """
            SELECT date, open, high, low, close, volume
            FROM market_data
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """

        # Format dates as strings for comparison
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        conn = self._get_connection()
        try:
            df = pd.read_sql_query(
                query,
                conn,
                params=(symbol, start_str, end_str),
                parse_dates=["date"]
            )

            if not df.empty:
                df.set_index("date", inplace=True)

            return df
        except Exception as e:
            logger.error(f"Failed to load bars for {symbol}: {e}")
            raise DataError(f"Failed to load data: {e}") from e

    def get_latest_date(self, symbol: str) -> Optional[datetime]:
        """Get the latest date available for a symbol.

        Args:
            symbol: Ticker symbol.

        Returns:
            Datetime of latest bar or None if no data exists.
        """
        query = "SELECT MAX(date) FROM market_data WHERE symbol = ?"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (symbol,))
            result = cursor.fetchone()[0]

            if result:
                return datetime.strptime(result, "%Y-%m-%d")
            return None
        except Exception as e:
            logger.error(f"Failed to get latest date for {symbol}: {e}")
            raise DataError(f"Database error: {e}") from e

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection
