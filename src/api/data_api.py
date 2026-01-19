"""User-friendly Data API for interactive data access.

This module provides a simple, high-level interface for fetching and
exploring market data. Designed for use in Jupyter notebooks and scripts.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.base import DataProvider
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

    def __init__(self, provider: DataProvider = None, db_path: str = None):
        """Initialize DataAPI.

        Args:
            provider: DataProvider instance (defaults to YFinanceProvider)
            db_path: Path to SQLite database (defaults to config)
        """
        self.provider = provider or YFinanceProvider()

        if db_path is None:
            # Use absolute path to project root relative to this file
            root_dir = Path(__file__).parent.parent.parent
            base_dir = root_dir / "data"
            base_dir.mkdir(exist_ok=True)
            db_path = str(base_dir / "market_data.db")

        self.db = DatabaseManager(db_path)

        # Load config for update_data method, as it's no longer passed directly
        # This assumes a default config path if not explicitly managed
        self.config = load_config("config/default.yaml")

        logger.debug("DataAPI initialized with %s and DB at %s", type(self.provider).__name__, db_path)

    def _parse_date(self, date_input: str | datetime) -> datetime:
        """Helper to parse date strings or return datetime objects."""
        if isinstance(date_input, str):
            return datetime.fromisoformat(date_input)
        return date_input

    def get_daily_bars(
        self,
        symbol: str,
        start: str | datetime,
        end: str | datetime,
    ) -> pd.DataFrame:
        """Get daily OHLCV bars for a symbol with smart caching.

        This method implements incremental fetching:
        1. Checks local database for existing data
        2. Fetches only MISSING chunks from provider
        3. Updates database with new data
        4. Returns combined dataframe

        Args:
            symbol: Ticker symbol
            start: Start date
            end: End date

        Returns:
            DataFrame with columns: open, high, low, close, volume (index: date)
        """
        start_dt = self._parse_date(start)
        end_dt = self._parse_date(end)

        logger.info("Requesting %s from %s to %s", symbol, start_dt.date(), end_dt.date())

        # 1. Load existing data from DB
        cached_df = self.db.load_bars(symbol, start_dt, end_dt)

        # Helper to fetch and save a range
        def fetch_and_save(s, e):
            chunk = self.provider.get_historical_bars(symbol, s, e)
            if not chunk.empty:
                # Normalize timezones to naive UTC-like to avoid mismatch with DB
                if chunk.index.tz is not None:
                    chunk.index = chunk.index.tz_localize(None)

                self.db.save_bars(chunk, symbol)
            return chunk

        # 2. Smart Fetching Logic
        if cached_df.empty:
            # Case A: No cache, fetch everything
            logger.info("No cache found. Fetching full range.")
            fetch_and_save(start_dt, end_dt)
        else:
            # Case B: Partial cache, fetch missing pieces
            cached_min = cached_df.index.min()
            cached_max = cached_df.index.max()

            # Fetch Pre-Cache Hole
            if start_dt < cached_min:
                pre_end = cached_min - timedelta(days=1)
                if start_dt <= pre_end:
                    # Use trading calendar to determine actual trading days in the gap
                    try:
                        trading_days = self.provider.get_trading_days(start_dt, pre_end)

                        if len(trading_days) > 0:
                            # Fetch from first to last trading day in the gap
                            actual_start = trading_days[0]
                            actual_end = trading_days[-1]

                            # yfinance is unreliable for single-day queries
                            # Extend range by a few days if only one trading day
                            if len(trading_days) == 1:
                                # Extend by 5 days to ensure we get data
                                actual_end = actual_end + timedelta(days=5)
                                logger.debug(
                                    "Single trading day detected, extending range to: %s",
                                    actual_end.date(),
                                )

                            logger.info(
                                "Fetching pre-cache gap: %s to %s (%d trading days)",
                                actual_start.date(),
                                actual_end.date(),
                                len(trading_days),
                            )
                            fetch_and_save(actual_start, actual_end)
                        else:
                            logger.debug(
                                "No trading days in pre-cache gap %s to %s, skipping fetch",
                                start_dt.date(),
                                pre_end.date(),
                            )
                    except Exception as e:
                        # Fallback to original logic if trading calendar fails
                        logger.warning(
                            "Trading calendar lookup failed, using date-based fetch: %s",
                            str(e),
                        )
                        fetch_and_save(start_dt, pre_end)

            # Fetch Post-Cache Hole
            if end_dt > cached_max:
                post_start = cached_max + timedelta(days=1)
                if post_start <= end_dt:
                    # Use trading calendar to determine actual trading days in the gap
                    # This avoids querying single non-trading days (weekends/holidays)
                    try:
                        trading_days = self.provider.get_trading_days(post_start, end_dt)

                        if len(trading_days) > 0:
                            # Fetch from first to last trading day in the gap
                            actual_start = trading_days[0]
                            actual_end = trading_days[-1]

                            # yfinance is unreliable for single-day queries
                            # Extend range by a few days if only one trading day
                            if len(trading_days) == 1:
                                # Extend by 5 days to ensure we get data
                                actual_end = actual_end + timedelta(days=5)
                                logger.debug(
                                    "Single trading day detected, extending range to: %s",
                                    actual_end.date(),
                                )

                            logger.info(
                                "Fetching post-cache gap: %s to %s (%d trading days)",
                                actual_start.date(),
                                actual_end.date(),
                                len(trading_days),
                            )
                            fetch_and_save(actual_start, actual_end)
                        else:
                            logger.debug(
                                "No trading days in post-cache gap %s to %s, skipping fetch",
                                post_start.date(),
                                end_dt.date(),
                            )
                    except Exception as e:
                        # Fallback to original logic if trading calendar fails
                        logger.warning(
                            "Trading calendar lookup failed, using date-based fetch: %s",
                            str(e),
                        )
                        fetch_and_save(post_start, end_dt)

        # 3. Reload Full Range from DB
        final_df = self.db.load_bars(symbol, start_dt, end_dt)

        if final_df.empty:
            logger.warning("No data available for %s", symbol)
            return final_df

        # Remove duplicates (keep last) and sort
        final_df = final_df[~final_df.index.duplicated(keep='last')]
        final_df = final_df.sort_index()

        logger.info("Returned %d bars for %s", len(final_df), symbol)
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
                latest_date = self.db.get_latest_date(symbol)
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
