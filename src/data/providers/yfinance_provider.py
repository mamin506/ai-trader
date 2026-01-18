"""YFinance data provider implementation.

This module implements the DataProvider interface using the yfinance library
to fetch historical market data from Yahoo Finance.
"""

from datetime import datetime

import pandas as pd
import yfinance as yf

from src.data.base import DataProvider
from src.utils.exceptions import DataProviderError, DataQualityError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class YFinanceProvider(DataProvider):
    """Yahoo Finance data provider implementation.

    Fetches historical OHLCV data from Yahoo Finance using the yfinance library.

    Example:
        >>> provider = YFinanceProvider()
        >>> data = provider.get_historical_bars(
        ...     "AAPL",
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
        >>> print(data.head())
    """

    def get_historical_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
            start_date: Start date for historical data (inclusive)
            end_date: End date for historical data (inclusive)

        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex with name "date"

        Raises:
            DataProviderError: If data fetching fails
            DataQualityError: If returned data is empty or invalid

        Example:
            >>> provider = YFinanceProvider()
            >>> data = provider.get_historical_bars("AAPL", start, end)
        """
        logger.info("Fetching data for %s from %s to %s", symbol, start_date, end_date)

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
        except Exception as e:
            error_msg = f"Failed to fetch data for {symbol}: {e}"
            logger.error(error_msg)
            raise DataProviderError(error_msg) from e

        # Validate data quality
        if df is None or df.empty:
            error_msg = f"No data returned for {symbol} from {start_date} to {end_date}"
            logger.error(error_msg)
            raise DataQualityError(error_msg)

        # Standardize column names (yfinance returns capitalized names)
        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )

        # Select only required columns
        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            error_msg = (
                f"Missing required columns for {symbol}: {missing_columns}. "
                f"Available columns: {list(df.columns)}"
            )
            logger.error(error_msg)
            raise DataQualityError(error_msg)

        df = df[required_columns]

        # Ensure index is named "date"
        df.index.name = "date"

        # Convert volume to integer (fillna with 0 before conversion)
        df["volume"] = df["volume"].fillna(0).astype(int)

        logger.info(
            "Successfully fetched %d bars for %s from %s to %s",
            len(df),
            symbol,
            df.index[0],
            df.index[-1],
        )

        return df
