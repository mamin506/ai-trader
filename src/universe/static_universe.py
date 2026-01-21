"""Static universe selector using pre-downloaded stock lists.

This module implements a universe selector that uses static stock listings
from AlphaVantage, applies filters, and ranks stocks to create a focused
trading universe.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.api.data_api import DataAPI
from src.universe.providers.alphavantage import AlphaVantageProvider
from src.universe.universe_selector import UniverseSelector
from src.utils.exceptions import DataProviderError

logger = logging.getLogger(__name__)


class StaticUniverseSelector(UniverseSelector):
    """Static universe selector using AlphaVantage listings.

    This selector:
    1. Fetches all US stocks from AlphaVantage (cached daily)
    2. Applies filters (exchange, liquidity, price, market cap)
    3. Ranks stocks by a scoring method
    4. Returns top N stocks

    For Phase 1.5, we use static filtering. Future phases can add:
    - Momentum ranking
    - Fundamental factors
    - Technical indicators
    - Machine learning scores
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        data_api: Optional[DataAPI] = None,
        # Filter parameters
        exchanges: Optional[list[str]] = None,
        min_price: float = 5.0,
        max_price: Optional[float] = None,
        min_avg_volume: float = 1_000_000,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
    ):
        """Initialize static universe selector.

        Args:
            cache_dir: Directory for caching listings
            data_api: DataAPI for price/volume data
            exchanges: List of exchanges (default: ['NASDAQ', 'NYSE'])
            min_price: Minimum stock price (default: $5)
            max_price: Maximum stock price (optional)
            min_avg_volume: Minimum avg daily volume (default: 1M shares)
            min_market_cap: Minimum market cap (optional)
            max_market_cap: Maximum market cap (optional)
        """
        # Default cache directory
        if cache_dir is None:
            cache_dir = Path("data/universe")

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize providers
        self.listings_provider = AlphaVantageProvider(cache_dir=cache_dir)
        self.data_api = data_api or DataAPI()

        # Filter parameters
        self.exchanges = exchanges or ["NASDAQ", "NYSE", "NYSE ARCA"]
        self.min_price = min_price
        self.max_price = max_price
        self.min_avg_volume = min_avg_volume
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap

        logger.debug("StaticUniverseSelector initialized")

    def select(
        self,
        date: Optional[datetime] = None,
        top_n: int = 100,
    ) -> list[str]:
        """Select stocks for the universe.

        Args:
            date: Date for selection (currently not used in Phase 1.5)
            top_n: Maximum number of stocks to select

        Returns:
            List of stock symbols

        Raises:
            DataProviderError: If data fetching fails
        """
        if date is None:
            date = datetime.now()

        logger.info(
            "Selecting universe for %s (top %d stocks)",
            date.strftime("%Y-%m-%d"),
            top_n,
        )

        # Step 1: Get all active stocks
        df = self.listings_provider.get_active_stocks(
            exchanges=self.exchanges,
            use_cache=True,
        )

        logger.info("Fetched %d active stocks from listings", len(df))

        # Step 2: Apply basic filters from listings
        df = self._apply_listing_filters(df)

        logger.info("After listing filters: %d stocks", len(df))

        # Step 3: Get market data for remaining stocks
        # (This is expensive, so we do it after initial filtering)
        df = self._enrich_with_market_data(df, date)

        logger.info("After enriching with market data: %d stocks", len(df))

        # Step 4: Apply market data filters
        df = self._apply_market_filters(df)

        logger.info("After market filters: %d stocks", len(df))

        # Step 5: Rank stocks
        df = self._rank_stocks(df)

        # Step 6: Select top N
        df = df.head(top_n)

        symbols = df["symbol"].tolist()

        logger.info("Selected %d stocks for universe", len(symbols))

        return symbols

    def get_universe_metadata(
        self,
        symbols: list[str],
        date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Get metadata for universe stocks.

        Args:
            symbols: List of stock symbols
            date: Date for metadata

        Returns:
            DataFrame with stock metadata
        """
        if not symbols:
            raise ValueError("Symbols list cannot be empty")

        if date is None:
            date = datetime.now()

        # Get listings data
        all_listings = self.listings_provider.fetch_listings(use_cache=True)
        df = all_listings[all_listings["symbol"].isin(symbols)].copy()

        # Enrich with market data
        df = self._enrich_with_market_data(df, date)

        return df

    def _apply_listing_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply filters based on listing data only.

        Args:
            df: DataFrame with listing data

        Returns:
            Filtered DataFrame
        """
        filtered = df.copy()

        # Filter by exchange (already done in get_active_stocks, but double-check)
        if self.exchanges:
            filtered = self.filter_by_exchange(filtered, self.exchanges)

        # Filter out symbols with special characters that are likely problematic
        # These are often warrants, preferred shares, etc.
        # Keep only: letters, numbers, and single hyphen (not at start/end)
        filtered = filtered[
            filtered['symbol'].str.match(r'^[A-Z][A-Z0-9]*(-[A-Z0-9]+)?$')
        ]

        logger.debug(f"After filtering invalid symbols: {len(filtered)} stocks")

        return filtered

    def _enrich_with_market_data(
        self, df: pd.DataFrame, date: datetime
    ) -> pd.DataFrame:
        """Enrich listings with market data (price, volume, market cap).

        This is the expensive operation that requires fetching data from YFinance.
        We do this after initial filtering to reduce API calls.

        Args:
            df: DataFrame with 'symbol' column
            date: Date for market data

        Returns:
            DataFrame enriched with market data columns
        """
        symbols = df["symbol"].tolist()

        if not symbols:
            return df

        # Get recent price data (last 30 days for avg volume calculation)
        from datetime import timedelta

        start_date = date - timedelta(days=30)
        end_date = date

        # Fetch data in batches to avoid overwhelming the API
        batch_size = 100
        market_data_list = []

        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i : i + batch_size]

            logger.debug(
                "Fetching market data for batch %d/%d (%d symbols)",
                i // batch_size + 1,
                (len(symbols) + batch_size - 1) // batch_size,
                len(batch_symbols),
            )

            # Fetch price data for each symbol in batch
            for symbol in batch_symbols:
                try:
                    symbol_df = self.data_api.get_daily_bars(
                        symbol,
                        start=start_date.strftime("%Y-%m-%d"),
                        end=end_date.strftime("%Y-%m-%d"),
                    )

                    if symbol_df.empty:
                        continue

                    # Get latest price
                    latest_price = symbol_df.iloc[-1]["close"]

                    # Calculate average volume (last 20 days)
                    avg_volume = symbol_df["volume"].tail(20).mean()

                    # Market cap requires shares outstanding (not available in yfinance daily data)
                    # For now, we'll skip market cap and add it in Phase 2 with fundamental data
                    market_cap = None

                    market_data_list.append(
                        {
                            "symbol": symbol,
                            "price": latest_price,
                            "avg_volume": avg_volume,
                            "market_cap": market_cap,
                        }
                    )

                except Exception as e:
                    logger.debug(
                        "Failed to fetch data for %s: %s", symbol, e
                    )
                    continue

        # Merge market data with listings
        if market_data_list:
            market_df = pd.DataFrame(market_data_list)
            df = df.merge(market_df, on="symbol", how="inner")
        else:
            # No market data available
            logger.warning("No market data fetched, returning empty DataFrame")
            return pd.DataFrame()

        return df

    def _apply_market_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply filters based on market data.

        Args:
            df: DataFrame with market data columns

        Returns:
            Filtered DataFrame
        """
        filtered = df.copy()

        # Filter by price
        if "price" in filtered.columns:
            filtered = self.filter_by_price(
                filtered,
                min_price=self.min_price,
                max_price=self.max_price,
            )

        # Filter by liquidity
        if "avg_volume" in filtered.columns:
            filtered = self.filter_by_liquidity(
                filtered,
                min_avg_volume=self.min_avg_volume,
            )

        # Filter by market cap (if available)
        if "market_cap" in filtered.columns and filtered["market_cap"].notna().any():
            filtered = self.filter_by_market_cap(
                filtered,
                min_market_cap=self.min_market_cap,
                max_market_cap=self.max_market_cap,
            )

        return filtered

    def _rank_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rank stocks by scoring criteria.

        Phase 1.5: Simple ranking by volume (liquidity preference)
        Phase 2+: Add momentum, fundamental factors, etc.

        Args:
            df: DataFrame with market data

        Returns:
            DataFrame sorted by rank (descending)
        """
        if df.empty:
            return df

        # Phase 1.5: Rank by average volume (higher is better)
        # This gives us the most liquid stocks
        df = df.sort_values("avg_volume", ascending=False)
        df["rank"] = range(1, len(df) + 1)

        return df
