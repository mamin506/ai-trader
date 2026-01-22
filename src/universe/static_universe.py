"""Static universe selector using pre-downloaded stock lists.

This module implements a universe selector that uses static stock listings
from AlphaVantage, applies filters, and ranks stocks to create a focused
trading universe.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.api.data_api import DataAPI
from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.storage.database import DatabaseManager
from src.universe.providers.alphavantage import AlphaVantageProvider
from src.universe.universe_selector import UniverseSelector
from src.utils.exceptions import DataProviderError

logger = logging.getLogger(__name__)


# Pre-defined list of known high-liquidity US stocks
# These are commonly traded large-cap stocks that are always active
# Used as a seed list when high filters are applied
# Note: This list should be periodically reviewed and updated
# Removed delisted/merged: SQ->BLOCK, ATVI (merged with MSFT), PXD (merged with XOM), PARA, U
HIGH_LIQUIDITY_SEEDS = [
    # Tech Giants
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
    # Semiconductors
    "AMD", "INTC", "AVGO", "QCOM", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "ON",
    # Software/Cloud
    "CRM", "ORCL", "ADBE", "NOW", "SNOW", "PLTR", "PANW", "CRWD", "ZS", "DDOG",
    # Other Tech
    "NFLX", "PYPL", "SHOP", "UBER", "ABNB", "DASH", "COIN", "RBLX", "NET", "MDB",
    # Finance
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "V", "MA",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "BMY", "GILD",
    # Consumer
    "WMT", "COST", "HD", "TGT", "LOW", "NKE", "SBUX", "MCD", "KO", "PEP",
    # Industrial
    "CAT", "DE", "BA", "GE", "HON", "MMM", "UPS", "FDX", "LMT", "RTX",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY", "MPC", "VLO", "PSX", "EOG", "DVN",
    # Communication
    "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA", "TTWO", "WBD", "NWSA",
    # ETFs
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "XLF", "XLK", "XLE", "XLV",
]


def is_valid_trading_symbol(symbol: str) -> bool:
    """Check if a symbol is a valid tradeable stock (not warrant, unit, etc.).

    Args:
        symbol: Stock ticker symbol

    Returns:
        True if symbol is likely a regular stock, False otherwise

    Rules:
        - Class shares: SYMBOL-A or SYMBOL-B (like BRK-A, BRK-B) are valid
        - Any other hyphenated symbol is likely warrant/unit/rights - invalid
        - 1-4 letter symbols are always valid (AAPL, MSFT, etc.)
        - 5-letter symbols ending in W, U, R are likely warrants/units/rights - invalid
        - Other 5-letter symbols are valid (GOOGL, NVDA, etc.)
    """
    if not symbol or not isinstance(symbol, str):
        return False

    # Class shares: SYMBOL-A or SYMBOL-B (like BRK-A, BRK-B)
    if re.match(r'^[A-Z]{1,4}-[AB]$', symbol):
        return True

    # Any other hyphenated symbol is likely warrant/unit
    if '-' in symbol:
        return False

    # Simple symbols: 1-4 uppercase letters (always valid)
    if re.match(r'^[A-Z]{1,4}$', symbol):
        return True

    # 5-letter symbols: exclude those ending in W, U, R (warrants, units, rights)
    if re.match(r'^[A-Z]{5}$', symbol):
        if symbol[-1] in ('W', 'U', 'R'):
            return False
        return True

    return False


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
        self.yf_provider = YFinanceProvider()

        # Database for checking cached data
        db_path = "data/market_data.db"
        self.db = DatabaseManager(db_path)

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
        use_seed_list: Optional[bool] = None,
    ) -> list[str]:
        """Select stocks for the universe.

        Args:
            date: Date for selection (currently not used in Phase 1.5)
            top_n: Maximum number of stocks to select
            use_seed_list: If True, start from pre-defined high-liquidity seeds.
                          If None (default), auto-detect based on filters.

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

        # Auto-detect if we should use seed list
        # Use seeds when high filters are set (reduces API calls significantly)
        if use_seed_list is None:
            use_seed_list = (
                self.min_avg_volume >= 5_000_000 or  # High volume filter
                self.min_price >= 50.0 or            # High price filter
                top_n <= 50                          # Small selection
            )

        if use_seed_list:
            logger.info(
                "Using seed list (high filters detected: min_vol=%s, min_price=%s)",
                f"{self.min_avg_volume:,.0f}",
                f"${self.min_price:.2f}",
            )
            # Start from seed list - much faster
            df = pd.DataFrame({"symbol": HIGH_LIQUIDITY_SEEDS})
        else:
            # Full listing scan - slower but more comprehensive
            logger.info("Using full listing scan (lower filters)")

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

        # Handle empty result from market data enrichment
        if df.empty or "symbol" not in df.columns:
            logger.warning(
                "No stocks with valid market data found. "
                "Try again later or use different filters."
            )
            return []

        logger.info("After enriching with market data: %d stocks", len(df))

        # Step 4: Apply market data filters
        df = self._apply_market_filters(df)

        logger.info("After market filters: %d stocks", len(df))

        if df.empty:
            logger.warning("No stocks passed market filters")
            return []

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

        # Filter out warrants, units, rights, and other non-common-stock symbols
        # using the is_valid_trading_symbol function
        before_count = len(filtered)
        filtered = filtered[filtered['symbol'].apply(is_valid_trading_symbol)]
        after_count = len(filtered)

        logger.info(
            "Filtered out %d invalid symbols (warrants, units, rights), "
            "%d stocks remaining",
            before_count - after_count,
            after_count
        )

        return filtered

    def _enrich_with_market_data(
        self, df: pd.DataFrame, date: datetime
    ) -> pd.DataFrame:
        """Enrich listings with market data (price, volume, market cap).

        Uses caching and batch fetching to minimize API calls and avoid
        rate limiting.

        Strategy:
        1. Check database for cached data first
        2. Batch fetch missing data from YFinance
        3. Save new data to cache

        Args:
            df: DataFrame with 'symbol' column
            date: Date for market data

        Returns:
            DataFrame enriched with market data columns
        """
        from datetime import timedelta

        symbols = df["symbol"].tolist()

        if not symbols:
            return df

        # Get recent price data (last 30 days for avg volume calculation)
        start_date = date - timedelta(days=30)
        end_date = date

        logger.info(
            "Enriching %d symbols with market data (%s to %s)",
            len(symbols),
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        market_data_list = []
        symbols_to_fetch = []

        # Step 1: Try to get data from cache first
        for symbol in symbols:
            try:
                cached_df = self.db.load_bars(symbol, start_date, end_date)

                # Need at least 10 days of data for reliable avg volume
                if not cached_df.empty and len(cached_df) >= 10:
                    # Have enough cached data
                    latest_price = cached_df.iloc[-1]["close"]
                    avg_volume = cached_df["volume"].mean()  # Use all available data

                    market_data_list.append(
                        {
                            "symbol": symbol,
                            "price": latest_price,
                            "avg_volume": avg_volume,
                            "market_cap": None,
                        }
                    )
                else:
                    # Need to fetch
                    symbols_to_fetch.append(symbol)

            except Exception:
                # Cache miss or error, need to fetch
                symbols_to_fetch.append(symbol)

        logger.info(
            "Found %d symbols in cache, need to fetch %d",
            len(market_data_list),
            len(symbols_to_fetch),
        )

        # Step 2: Batch fetch missing data
        if symbols_to_fetch:
            import time

            # Use smaller batches to avoid rate limiting
            # YFinance allows ~2000 requests/hour = ~33 per minute
            # With batch of 20 and 2 second delay = 600 symbols/hour
            batch_size = 20

            for i in range(0, len(symbols_to_fetch), batch_size):
                batch_symbols = symbols_to_fetch[i: i + batch_size]

                logger.info(
                    "Fetching batch %d/%d (%d symbols)...",
                    i // batch_size + 1,
                    (len(symbols_to_fetch) + batch_size - 1) // batch_size,
                    len(batch_symbols),
                )

                try:
                    # Use batch fetching
                    price_data = self.yf_provider.get_historical_bars_batch(
                        batch_symbols,
                        start_date,
                        end_date,
                    )

                    # Process results
                    for symbol, symbol_df in price_data.items():
                        # Need at least 10 days for reliable average
                        if symbol_df.empty or len(symbol_df) < 10:
                            logger.debug(
                                "Skipping %s: only %d rows",
                                symbol,
                                len(symbol_df) if not symbol_df.empty else 0
                            )
                            continue

                        # Get latest price
                        latest_price = symbol_df.iloc[-1]["close"]

                        # Calculate average volume (use all available data)
                        avg_volume = symbol_df["volume"].mean()

                        market_data_list.append(
                            {
                                "symbol": symbol,
                                "price": latest_price,
                                "avg_volume": avg_volume,
                                "market_cap": None,
                            }
                        )

                        # Save to cache
                        try:
                            self.db.save_bars(symbol_df, symbol)
                        except Exception as e:
                            logger.debug("Failed to cache %s: %s", symbol, e)

                    logger.info(
                        "Batch complete: %d/%d successful",
                        len(price_data),
                        len(batch_symbols),
                    )

                    # Add delay between batches to respect rate limits
                    if i + batch_size < len(symbols_to_fetch):
                        logger.debug("Waiting 2s before next batch...")
                        time.sleep(2)

                except Exception as e:
                    logger.warning("Batch fetch failed: %s", e)
                    # On error, wait longer before retry
                    time.sleep(5)
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
