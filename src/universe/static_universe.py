"""Static universe selector using seed list.

This module implements a universe selector that starts from a curated seed list
of stocks, applies filters, and ranks stocks to create a focused trading universe.

The seed list is stored in data/seed_list.json and should be updated biweekly
using Finviz screener.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from src.api.data_api import DataAPI
from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.storage.database import DatabaseManager
from src.universe.universe_selector import UniverseSelector

logger = logging.getLogger(__name__)


def load_seed_list(seed_file: Optional[Path] = None) -> list[str]:
    """Load seed list from JSON file.

    Args:
        seed_file: Path to seed list JSON file (default: data/seed_list.json)

    Returns:
        List of stock symbols

    Raises:
        FileNotFoundError: If seed file doesn't exist
        ValueError: If seed file is invalid
    """
    if seed_file is None:
        seed_file = Path("data/seed_list.json")

    if not seed_file.exists():
        raise FileNotFoundError(
            f"Seed list file not found: {seed_file}\n"
            "Please create the seed list file or run the screener to generate it."
        )

    try:
        with open(seed_file, "r") as f:
            data = json.load(f)

        if "seeds" not in data:
            raise ValueError("Seed list file must contain 'seeds' key")

        symbols = data["seeds"]
        logger.info("Loaded %d symbols from seed list", len(symbols))

        return symbols

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in seed list file: {e}") from e


def save_seed_list(
    symbols: list[str],
    seed_file: Optional[Path] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Save seed list to JSON file.

    Args:
        symbols: List of stock symbols
        seed_file: Path to seed list JSON file (default: data/seed_list.json)
        metadata: Optional metadata dict to include
    """
    if seed_file is None:
        seed_file = Path("data/seed_list.json")

    seed_file.parent.mkdir(parents=True, exist_ok=True)

    # Prepare metadata
    if metadata is None:
        metadata = {}

    metadata.update(
        {
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "total_count": len(symbols),
        }
    )

    data = {"metadata": metadata, "seeds": sorted(symbols)}

    with open(seed_file, "w") as f:
        json.dump(data, f, indent=2)

    logger.info("Saved %d symbols to seed list", len(symbols))


class StaticUniverseSelector(UniverseSelector):
    """Static universe selector using seed list.

    This selector:
    1. Loads stocks from seed list (data/seed_list.json)
    2. Applies filters (liquidity, price, market cap)
    3. Ranks stocks by a scoring method
    4. Returns top N stocks

    The seed list should be updated biweekly using Finviz screener.
    """

    def __init__(
        self,
        seed_file: Optional[Path] = None,
        data_api: Optional[DataAPI] = None,
        # Filter parameters
        min_price: float = 5.0,
        max_price: Optional[float] = None,
        min_avg_volume: float = 1_000_000,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
    ):
        """Initialize static universe selector.

        Args:
            seed_file: Path to seed list JSON file (default: data/seed_list.json)
            data_api: DataAPI for price/volume data
            min_price: Minimum stock price (default: $5)
            max_price: Maximum stock price (optional)
            min_avg_volume: Minimum avg daily volume (default: 1M shares)
            min_market_cap: Minimum market cap (optional)
            max_market_cap: Maximum market cap (optional)
        """
        self.seed_file = seed_file or Path("data/seed_list.json")
        self.data_api = data_api or DataAPI()
        self.yf_provider = YFinanceProvider()

        # Database for checking cached data
        db_path = "data/market_data.db"
        self.db = DatabaseManager(db_path)

        # Filter parameters
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
            FileNotFoundError: If seed list file doesn't exist
        """
        if date is None:
            date = datetime.now()

        logger.info(
            "Selecting universe for %s (top %d stocks)",
            date.strftime("%Y-%m-%d"),
            top_n,
        )

        # Step 1: Load seed list
        symbols = load_seed_list(self.seed_file)
        df = pd.DataFrame({"symbol": symbols})

        logger.info("Loaded %d stocks from seed list", len(df))

        # Step 2: Get market data for symbols
        df = self._enrich_with_market_data(df, date)

        # Handle empty result from market data enrichment
        if df.empty or "symbol" not in df.columns:
            logger.warning(
                "No stocks with valid market data found. "
                "Try again later or use different filters."
            )
            return []

        logger.info("After enriching with market data: %d stocks", len(df))

        # Step 3: Apply market data filters
        df = self._apply_market_filters(df)

        logger.info("After market filters: %d stocks", len(df))

        if df.empty:
            logger.warning("No stocks passed market filters")
            return []

        # Step 4: Rank stocks
        df = self._rank_stocks(df)

        # Step 5: Select top N
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

        # Create dataframe from symbols
        df = pd.DataFrame({"symbol": symbols})

        # Enrich with market data
        df = self._enrich_with_market_data(df, date)

        return df

    def _enrich_with_market_data(
        self, df: pd.DataFrame, date: datetime
    ) -> pd.DataFrame:
        """Enrich symbols with market data (price, volume, market cap).

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
                    avg_volume = cached_df["volume"].mean()

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
                batch_symbols = symbols_to_fetch[i : i + batch_size]

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
                                len(symbol_df) if not symbol_df.empty else 0,
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

        # Merge market data with symbols
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
