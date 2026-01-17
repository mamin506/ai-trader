"""User-friendly Data API for interactive data access.

This module provides a simple, high-level interface for fetching and
exploring market data. Designed for use in Jupyter notebooks and scripts.
"""

from datetime import datetime, timedelta

import pandas as pd

from src.data.providers.yfinance_provider import YFinanceProvider
from src.utils.logging import get_logger

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

    def __init__(self):
        """Initialize DataAPI with default YFinance provider."""
        self.provider = YFinanceProvider()
        logger.debug("DataAPI initialized with YFinanceProvider")

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

        logger.info(f"Fetching daily bars for {symbol} from {start} to {end}")
        return self.provider.get_historical_bars(symbol, start, end)

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

        logger.info(f"Fetching latest {days} days for {symbol}")
        data = self.provider.get_historical_bars(symbol, start, end)

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

        logger.info(f"Fetching data for {len(symbols)} symbols")

        result = {}
        for symbol in symbols:
            try:
                result[symbol] = self.provider.get_historical_bars(symbol, start, end)
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                # Continue with other symbols

        return result

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
