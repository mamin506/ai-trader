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

    def get_historical_bars_batch(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical OHLCV bars for multiple symbols at once.

        This is more efficient than calling get_historical_bars() for each symbol
        individually, as it reduces API calls and avoids rate limiting.

        Args:
            symbols: List of stock ticker symbols
            start_date: Start date for historical data (inclusive)
            end_date: End date for historical data (inclusive)

        Returns:
            Dict mapping symbol to DataFrame with OHLCV data
            Symbols with no data or errors are omitted from result

        Example:
            >>> provider = YFinanceProvider()
            >>> data = provider.get_historical_bars_batch(
            ...     ["AAPL", "MSFT", "GOOGL"],
            ...     start, end
            ... )
            >>> print(data["AAPL"].head())
        """
        if not symbols:
            return {}

        logger.info("Fetching data for %d symbols from %s to %s",
                   len(symbols), start_date, end_date)

        result = {}

        try:
            # Use yfinance download for batch fetching
            # This is much more efficient than individual ticker.history() calls
            import yfinance as yf

            # Download data for all symbols at once
            data = yf.download(
                tickers=' '.join(symbols),
                start=start_date,
                end=end_date,
                group_by='ticker',
                auto_adjust=False,
                progress=False,
                threads=True,  # Enable multithreading
            )

            # Process results
            if len(symbols) == 1:
                # Single symbol returns different format
                symbol = symbols[0]
                if not data.empty:
                    df = data.copy()
                    df = self._standardize_dataframe(df, symbol)
                    if df is not None:
                        result[symbol] = df
            else:
                # Multiple symbols
                for symbol in symbols:
                    try:
                        if symbol in data.columns.levels[0]:
                            symbol_data = data[symbol]
                            if not symbol_data.empty:
                                df = self._standardize_dataframe(symbol_data, symbol)
                                if df is not None:
                                    result[symbol] = df
                    except (KeyError, AttributeError, IndexError):
                        logger.debug("No data for %s", symbol)
                        continue

            logger.info("Successfully fetched data for %d/%d symbols",
                       len(result), len(symbols))

        except Exception as e:
            logger.error("Batch fetch failed: %s", e)
            # Fall back to individual fetching if batch fails
            logger.info("Falling back to individual symbol fetching...")
            for symbol in symbols:
                try:
                    df = self.get_historical_bars(symbol, start_date, end_date)
                    result[symbol] = df
                except Exception:
                    continue

        return result

    def _standardize_dataframe(
        self, df: pd.DataFrame, symbol: str
    ) -> pd.DataFrame | None:
        """Standardize a DataFrame to required format.

        Args:
            df: Raw DataFrame from yfinance
            symbol: Stock symbol

        Returns:
            Standardized DataFrame or None if data is invalid
        """
        if df is None or df.empty:
            return None

        # Standardize column names
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
            logger.debug("Missing columns for %s: %s", symbol, missing_columns)
            return None

        df = df[required_columns].copy()

        # Ensure index is named "date"
        df.index.name = "date"

        # Convert volume to integer
        df["volume"] = df["volume"].fillna(0).astype(int)

        # Remove rows with NaN values
        df = df.dropna()

        if df.empty:
            return None

        return df

    def get_trading_days(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DatetimeIndex:
        """Get trading days for NYSE from exchange_calendars.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DatetimeIndex containing valid trading days.
        """
        try:
            import exchange_calendars as xcals

            # Use XNYS (New York Stock Exchange) as the standard
            nyse = xcals.get_calendar("XNYS")

            # Get trading sessions for the date range
            sessions = nyse.sessions_in_range(
                start=pd.Timestamp(start_date),
                end=pd.Timestamp(end_date)
            )

            # Return as DatetimeIndex normalized to midnight (naive datetime)
            return pd.DatetimeIndex([d.to_pydatetime().replace(tzinfo=None) for d in sessions])

        except ImportError as e:
            logger.error("exchange_calendars not installed")
            raise DataProviderError(
                "exchange_calendars is required for validation. Please install it."
            ) from e
        except Exception as e:
            error_msg = f"Failed to get trading days: {e}"
            logger.error(error_msg)
            raise DataProviderError(error_msg) from e
