#!/usr/bin/env python3
"""Manual test with known symbols."""

from datetime import datetime
from src.api.universe_api import UniverseAPI
from src.universe.static_universe import StaticUniverseSelector
from src.universe.providers.alphavantage import AlphaVantageProvider
import pandas as pd

print("Manual Universe Selection Test with Known Symbols")
print("=" * 70)

# Test with manually specified symbols (bypass AlphaVantage completely for now)
print("\n1. Creating selector...")
selector = StaticUniverseSelector(
    min_price=10.0,
    min_avg_volume=5_000_000,
)

print("\n2. Manually creating mock listings for known symbols...")
# Create a mock listings DataFrame with known good symbols
mock_listings = pd.DataFrame({
    'symbol': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'SPY'],
    'name': ['Apple', 'Microsoft', 'Google', 'Amazon', 'NVIDIA', 'Tesla', 'Meta', 'S&P 500 ETF'],
    'exchange': ['NASDAQ', 'NASDAQ', 'NASDAQ', 'NASDAQ', 'NASDAQ', 'NASDAQ', 'NASDAQ', 'NYSE ARCA'],
    'assetType': ['Stock', 'Stock', 'Stock', 'Stock', 'Stock', 'Stock', 'Stock', 'ETF'],
    'status': ['Active', 'Active', 'Active', 'Active', 'Active', 'Active', 'Active', 'Active'],
})

# Filter for stocks only
stocks = mock_listings[mock_listings['assetType'] == 'Stock']

print(f"\n3. Enriching {len(stocks)} stocks with market data...")
date = datetime.now()

# Call the enrichment method
enriched_df = selector._enrich_with_market_data(stocks, date)

print(f"   ✓ Enriched {len(enriched_df)} stocks with market data")

if not enriched_df.empty:
    print("\n4. Applying market filters...")
    filtered_df = selector._apply_market_filters(enriched_df)
    print(f"   ✓ {len(filtered_df)} stocks passed filters")

    print("\n5. Ranking stocks...")
    ranked_df = selector._rank_stocks(filtered_df)

    if not ranked_df.empty:
        print(f"   ✓ Ranked {len(ranked_df)} stocks")
        print("\n6. Top stocks:")
        for idx, row in ranked_df.head(5).iterrows():
            print(f"   {row['rank']:2d}. {row['symbol']:6s} - "
                  f"Price: ${row['price']:7.2f}, "
                  f"Vol: {row['avg_volume']:,.0f}")
    else:
        print("   ✗ No stocks after ranking")
else:
    print("   ✗ No stocks enriched with market data")

print("\n" + "=" * 70)
print("Test complete!")
