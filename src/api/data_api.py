"""User-friendly Data API for interactive data access.

This module provides a simple, high-level interface for fetching and
exploring market data. Designed for use in Jupyter notebooks and scripts.
"""

from datetime import datetime, timedelta

import pandas as pd

from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.storage.database import DatabaseManager
from src.utils.logging import get_logger
from src.utils.config import load_config

logger = get_logger(__name__)


class DataAPI:
    """High-level API for market data access.

    Provides simple methods for fetching and exploring historical market data.
    Uses YFinance by default, but can be configured to use other providers.

    Example:
        >>> from src.api.data_api import DataAPI
        >>> api = DataAPI()
        >>> data = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-31")
        >>> print(data.head())

        # Or use datetime objects
        >>> from datetime import datetime
        >>> data = api.get_daily_bars(
        ...     "AAPL",
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
    """

    def __init__(self, config_path: str = "config/default.yaml"):
        """Initialize DataAPI with default YFinance provider and database storage."""
        self.config = load_config(config_path) if config_path else {}
        # Default to YFinance for now, can be made configurable later
        self.provider = YFinanceProvider()

        # Initialize storage
        db_path = self.config.get("data", {}).get("db_path", "data/market_data.db")
        self.storage = DatabaseManager(db_path)

        logger.debug("DataAPI initialized with YFinanceProvider and DB at %s", db_path)

    def get_daily_bars(
        self,
        symbol: str,
        start: str | datetime,
        end: str | datetime,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars for a symbol.

        Convenience method that accepts both string dates and datetime objects.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
            start: Start date as string "YYYY-MM-DD" or datetime object
            end: End date as string "YYYY-MM-DD" or datetime object

        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex with name "date"

        Example:
            >>> api = DataAPI()
            >>> data = api.get_daily_bars("AAPL", "2024-01-01", "2024-01-31")
            >>> print(f"Fetched {len(data)} days of data")
        """
        # Convert string dates to datetime if needed
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        logger.info("Fetching daily bars for %s from %s to %s", symbol, start, end)

        start_requested = start
        end_requested = end

        # 1. Try to load from database first
        cached_data = pd.DataFrame()
        try:
            cached_data = self.storage.load_bars(symbol, start_requested, end_requested)
        except Exception as e:
            logger.warning("Failed to load from cache: %s", e)

        # Helper to fetch and save data
        def fetch_and_save(s, e):
            chunk = self.provider.get_historical_bars(symbol, s, e)
            if not chunk.empty:
                # Ensure index is timezone-naive to match database cache
                if chunk.index.tz is not None:
                    chunk.index = chunk.index.tz_localize(None)

                try:
                    self.storage.save_bars(chunk, symbol)
                except Exception as ex:
                    logger.error("Failed to save to cache: %s", ex)
            return chunk

        chunks = []
        if not cached_data.empty:
            chunks.append(cached_data)

            # Check for missing data before the cache
            cached_min_date = cached_data.index.min()
            if start_requested < cached_min_date:
                pre_end = cached_min_date - timedelta(days=1)
                if pre_end >= start_requested:
                    logger.info("Fetching missing pre-cache data for %s from %s to %s", symbol, start_requested, pre_end)
                    chunks.append(fetch_and_save(start_requested, pre_end))

            # Check for missing data after the cache
            cached_max_date = cached_data.index.max()
            if end_requested > cached_max_date:
                post_start = cached_max_date + timedelta(days=1)
                if post_start <= end_requested:
                    logger.info("Fetching missing post-cache data for %s from %s to %s", symbol, post_start, end_requested)
                    chunks.append(fetch_and_save(post_start, end_requested))
        else:
            # No cache, fetch everything
            logger.info("No cached data found, fetching full range for %s", symbol)
            chunks.append(fetch_and_save(start_requested, end_requested))

        # Merge all chunks
        if not chunks:
            return pd.DataFrame()

        final_df = pd.concat(chunks)
        # Remove duplicates (keep last) and sort
        final_df = final_df[~final_df.index.duplicated(keep='last')].sort_index()

        return final_df

    def get_latest(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Fetch the most recent N days of data.

        Convenience method for getting recent historical data.

        Args:
            symbol: Stock ticker symbol
            days: Number of recent trading days to fetch (default: 30)

        Returns:
            DataFrame with most recent N days of OHLCV data

        Example:
            >>> api = DataAPI()
            >>> recent = api.get_latest("AAPL", days=7)
            >>> print("Last week's closing prices:")
            >>> print(recent["close"])
        """
        end = datetime.now()
        # Fetch extra days to account for weekends/holidays
        start = end - timedelta(days=days * 2)

        logger.info("Fetching latest %s days for %s", days, symbol)
        # Use get_daily_bars to benefit from caching
        data = self.get_daily_bars(symbol, start, end)

        # Return only the requested number of days
        return data.tail(days)

    def get_multiple_symbols(
        self,
        symbols: list[str],
        start: str | datetime,
        end: str | datetime,
    ) -> dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols.

        Args:
            symbols: List of ticker symbols
            start: Start date
            end: End date

        Returns:
            Dictionary mapping symbol to DataFrame

        Example:
            >>> api = DataAPI()
            >>> data = api.get_multiple_symbols(
            ...     ["AAPL", "GOOGL", "MSFT"],
            ...     "2024-01-01",
            ...     "2024-01-31"
            ... )
            >>> for symbol, df in data.items():
            ...     print(f"{symbol}: {len(df)} bars")
        """
        # Convert string dates to datetime if needed
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        logger.info("Fetching data for %s symbols", len(symbols))

        result = {}
        for symbol in symbols:
            try:
                result[symbol] = self.provider.get_historical_bars(symbol, start, end)
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", symbol, e)
                # Continue with other symbols

        return result

    def update_data(self, symbols: list[str] | None = None) -> None:
        """Update data for specified symbols (or all in config).

        Args:
            symbols: List of symbols to update.
        """
        if symbols is None:
            # Fallback to a default list if config is missing universe
            symbols = (
                self.config.get("strategy", {})
                .get("parameters", {})
                .get("universe", ["AAPL", "SPY"])
            )

        end = datetime.now()
        start = end - timedelta(days=7) # Update last week by default

        # Check latest date in DB for each symbol to optimize start date
        for symbol in symbols:
            try:
                latest_date = self.storage.get_latest_date(symbol)
                if latest_date:
                    sym_start = latest_date + timedelta(days=1)
                    if sym_start < end:
                         self.get_daily_bars(symbol, sym_start, end)
                else:
                    self.get_daily_bars(symbol, start, end)
            except Exception as e:
                logger.error("Error updating %s: %s", symbol, e)

    def info(self, symbol: str) -> None:
        """Print summary information about available data for a symbol.

        Args:
            symbol: Stock ticker symbol

        Example:
            >>> api = DataAPI()
            >>> api.info("AAPL")
            Symbol: AAPL
            Latest 30 days: 21 trading days
            Date range: 2024-01-02 to 2024-01-31
            ...
        """
        try:
            data = self.get_latest(symbol, days=30)
            print(f"Symbol: {symbol}")
            print(f"Latest 30 days: {len(data)} trading days")
            print(f"Date range: {data.index[0].date()} to {data.index[-1].date()}")
            print(f"\nLatest close: ${data['close'].iloc[-1]:.2f}")
            print(f"30-day high: ${data['high'].max():.2f}")
            print(f"30-day low: ${data['low'].min():.2f}")
            print(f"Average volume: {data['volume'].mean():,.0f}")
        except Exception as e:
            print(f"Error fetching info for {symbol}: {e}")
