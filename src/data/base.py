"""Abstract base class for market data providers.

This module defines the DataProvider interface that all concrete data providers
must implement.
"""

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class DataProvider(ABC):
    """Abstract interface for market data providers.

    All concrete data providers (YFinance, Alpaca, etc.) must implement this
    interface to ensure consistent data access patterns across the application.

    Example:
        >>> class MyProvider(DataProvider):
        ...     def get_historical_bars(self, symbol, start_date, end_date):
        ...         # Implementation here
        ...         pass
    """

    @abstractmethod
    def get_historical_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars for a symbol.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
            start_date: Start date for historical data (inclusive)
            end_date: End date for historical data (inclusive)

        Returns:
            DataFrame with columns:
                - date (datetime): Trading date (index)
                - open (float): Opening price
                - high (float): High price
                - low (float): Low price
                - close (float): Closing price
                - volume (int): Trading volume

        Raises:
            DataProviderError: If data fetching fails
            DataQualityError: If returned data fails quality checks

        Example:
            >>> provider = YFinanceProvider()
            >>> data = provider.get_historical_bars(
            ...     "AAPL",
            ...     datetime(2024, 1, 1),
            ...     datetime(2024, 12, 31)
            ... )
            >>> print(data.head())
                        open   high    low  close    volume
            date
            2024-01-02  185.0  186.0  184.0  185.5  50000000
        """
        pass

    @abstractmethod
    def get_trading_days(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DatetimeIndex:
        """Get list of trading days between start and end date (inclusive).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DatetimeIndex containing valid trading days.
        """
        pass
