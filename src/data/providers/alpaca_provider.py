"""Alpaca data provider implementation.

This module implements the DataProvider interface using the Alpaca API
to fetch historical and real-time market data.
"""

from datetime import datetime

import pandas as pd
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from src.data.base import DataProvider
from src.utils.alpaca_client import AlpacaClient
from src.utils.exceptions import DataProviderError, DataQualityError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AlpacaProvider(DataProvider):
    """Alpaca data provider implementation.

    Fetches historical OHLCV data and real-time quotes from Alpaca API.

    Example:
        >>> client = AlpacaClient.from_env()
        >>> provider = AlpacaProvider(client)
        >>> data = provider.get_historical_bars(
        ...     "AAPL",
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
    """

    def __init__(self, alpaca_client: AlpacaClient):
        """Initialize Alpaca provider.

        Args:
            alpaca_client: AlpacaClient instance for API access
        """
        self.client = alpaca_client
        self.data_client = alpaca_client.get_data_client()
        logger.info("AlpacaProvider initialized")

    def get_historical_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch historical daily bars from Alpaca.

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
            >>> provider = AlpacaProvider(client)
            >>> data = provider.get_historical_bars("AAPL", start, end)
        """
        logger.info(
            "Fetching Alpaca data for %s from %s to %s",
            symbol,
            start_date,
            end_date,
        )

        try:
            # Create request for daily bars
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
            )

            # Fetch data with retry logic
            bars = self.client.with_retry(
                self.data_client.get_stock_bars,
                request,
            )

            # Extract data for the symbol
            if symbol not in bars:
                raise DataQualityError(
                    f"No data returned for {symbol} from {start_date} to {end_date}"
                )

            symbol_bars = bars[symbol]

            if not symbol_bars or len(symbol_bars) == 0:
                raise DataQualityError(
                    f"No bars returned for {symbol} from {start_date} to {end_date}"
                )

            # Convert to DataFrame
            df = symbol_bars.df

            # Validate data quality
            if df is None or df.empty:
                raise DataQualityError(
                    f"Empty DataFrame for {symbol} from {start_date} to {end_date}"
                )

            # Standardize column names (Alpaca returns lowercase)
            # DataFrame columns: symbol, open, high, low, close, volume, trade_count, vwap
            required_columns = ["open", "high", "low", "close", "volume"]
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                error_msg = (
                    f"Missing required columns for {symbol}: {missing_columns}. "
                    f"Available columns: {list(df.columns)}"
                )
                logger.error(error_msg)
                raise DataQualityError(error_msg)

            # Select only required columns
            df = df[required_columns].copy()

            # Ensure index is DatetimeIndex and named "date"
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            df.index.name = "date"

            # Remove timezone info to match existing DataProvider interface
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Convert volume to integer (fillna with 0 before conversion)
            df["volume"] = df["volume"].fillna(0).astype(int)

            # Remove rows with NaN values
            df = df.dropna()

            if df.empty:
                raise DataQualityError(
                    f"All data contains NaN for {symbol} from {start_date} to {end_date}"
                )

            logger.info(
                "Successfully fetched %d bars for %s from %s to %s",
                len(df),
                symbol,
                df.index[0],
                df.index[-1],
            )

            return df

        except DataQualityError:
            # Re-raise data quality errors as-is
            raise

        except Exception as e:
            error_msg = f"Failed to fetch Alpaca data for {symbol}: {e}"
            logger.error(error_msg)
            raise DataProviderError(error_msg) from e

    def get_latest_quote(self, symbol: str) -> dict:
        """Get latest quote (real-time price) from Alpaca.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with quote information:
            {
                'symbol': str,
                'bid': float,
                'ask': float,
                'last': float,  # Midpoint of bid/ask
                'timestamp': datetime,
            }

        Raises:
            DataProviderError: If quote fetching fails

        Example:
            >>> quote = provider.get_latest_quote("AAPL")
            >>> print(f"Last price: ${quote['last']:.2f}")
        """
        logger.info("Fetching latest quote for %s", symbol)

        try:
            # Create request for latest quote
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)

            # Fetch quote with retry logic
            quotes = self.client.with_retry(
                self.data_client.get_stock_latest_quote,
                request,
            )

            # Extract quote for the symbol
            if symbol not in quotes:
                raise DataProviderError(f"No quote returned for {symbol}")

            quote = quotes[symbol]

            # Extract quote data
            bid = float(quote.bid_price)
            ask = float(quote.ask_price)
            last = (bid + ask) / 2.0  # Midpoint
            timestamp = quote.timestamp

            # Remove timezone info
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)

            result = {
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "last": last,
                "timestamp": timestamp,
            }

            logger.info(
                "Latest quote for %s: bid=%.2f, ask=%.2f, last=%.2f",
                symbol,
                bid,
                ask,
                last,
            )

            return result

        except Exception as e:
            error_msg = f"Failed to fetch latest quote for {symbol}: {e}"
            logger.error(error_msg)
            raise DataProviderError(error_msg) from e

    def get_trading_days(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DatetimeIndex:
        """Get trading days for NYSE from exchange_calendars.

        Uses the same implementation as YFinanceProvider for consistency.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DatetimeIndex containing valid trading days

        Raises:
            DataProviderError: If trading days cannot be fetched
        """
        try:
            import exchange_calendars as xcals

            # Use XNYS (New York Stock Exchange) as the standard
            nyse = xcals.get_calendar("XNYS")

            # Get trading sessions for the date range
            sessions = nyse.sessions_in_range(
                start=pd.Timestamp(start_date), end=pd.Timestamp(end_date)
            )

            # Return as DatetimeIndex normalized to midnight (naive datetime)
            return pd.DatetimeIndex(
                [d.to_pydatetime().replace(tzinfo=None) for d in sessions]
            )

        except ImportError as e:
            logger.error("exchange_calendars not installed")
            raise DataProviderError(
                "exchange_calendars is required for validation. "
                "Please install it."
            ) from e
        except Exception as e:
            error_msg = f"Failed to get trading days: {e}"
            logger.error(error_msg)
            raise DataProviderError(error_msg) from e
