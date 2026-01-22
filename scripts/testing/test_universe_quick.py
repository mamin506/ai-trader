#!/usr/bin/env python3
"""Quick test of Universe Selection Layer."""

from datetime import datetime, timedelta
from src.api.universe_api import UniverseAPI

print("Testing Universe Selection Layer...")
print("=" * 60)

# Test 1: Refresh cache
print("\n1. Refreshing AlphaVantage cache...")
api = UniverseAPI()

try:
    count = api.refresh_listings_cache()
    print(f"✓ Fetched {count} stock listings")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Select small universe with very restrictive filters
print("\n2. Selecting universe (very restrictive filters)...")
try:
    # Use AAPL, MSFT, GOOGL by setting very specific filters
    symbols = api.select_universe(
        name='test_quick',
        top_n=5,
        min_price=100.0,      # High price to reduce candidates
        min_avg_volume=20_000_000,  # Very high volume
        save=True,
    )

    print(f"✓ Selected {len(symbols)} symbols")
    print(f"  Symbols: {symbols}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Load saved universe
print("\n3. Loading saved universe...")
try:
    loaded = api.load_universe('test_quick')
    print(f"✓ Loaded {len(loaded)} symbols")
    print(f"  Symbols: {loaded}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Get available dates
print("\n4. Getting available dates...")
try:
    dates = api.get_universe_dates('test_quick')
    print(f"✓ Found {len(dates)} dates")
    if dates:
        print(f"  Latest: {dates[0]}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("Test complete!")
