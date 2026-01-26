#!/usr/bin/env python3
"""Update seed list using Finviz screener.

This script should be run biweekly (every 2 weeks) to refresh the seed list
with actively traded, liquid stocks from the US markets.

Usage:
    python scripts/update_seed_list.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from finviz.screener import Screener

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.universe.static_universe import load_seed_list, save_seed_list


def screen_stocks() -> list[str]:
    """Screen for high-quality, liquid stocks using Finviz.

    Strategy:
    1. Get mega cap stocks ($200B+)
    2. Get large cap stocks ($10B-$200B)
    3. Combine and deduplicate
    4. Filter for liquidity (volume > 2M)

    Returns:
        List of stock symbols
    """
    print("\n" + "=" * 80)
    print("SCREENING STOCKS WITH FINVIZ")
    print("=" * 80)

    all_symbols = set()

    # Step 1: Get mega cap stocks ($200B+)
    print("\n[1/2] Fetching mega cap stocks ($200B+)...")
    try:
        screener_mega = Screener(
            filters=["cap_mega"],  # $200B+
            table="Overview",
            order="-marketcap",
        )

        mega_df = pd.DataFrame(screener_mega.data)
        mega_symbols = set(mega_df["Ticker"].tolist())

        print(f"✅ Found {len(mega_symbols)} mega cap stocks")

        # Filter for volume > 2M
        if "Volume" in mega_df.columns:
            mega_df["VolumeNumeric"] = mega_df["Volume"].apply(
                lambda x: int(str(x).replace(",", "")) if pd.notna(x) else 0
            )
            mega_df_filtered = mega_df[mega_df["VolumeNumeric"] > 2_000_000]
            mega_symbols = set(mega_df_filtered["Ticker"].tolist())
            print(f"   After volume filter (>2M): {len(mega_symbols)} stocks")

        all_symbols.update(mega_symbols)

    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch mega cap stocks: {e}")

    # Wait to avoid rate limiting
    print("\n⏳ Waiting 5 seconds to avoid rate limiting...")
    time.sleep(5)

    # Step 2: Get large cap stocks ($10B-$200B)
    print("\n[2/2] Fetching large cap stocks ($10B-$200B)...")
    try:
        screener_large = Screener(
            filters=["cap_large"],  # $10B-$200B
            table="Overview",
            order="-marketcap",
        )

        large_df = pd.DataFrame(screener_large.data)
        large_symbols = set(large_df["Ticker"].tolist())

        print(f"✅ Found {len(large_symbols)} large cap stocks")

        # Filter for volume > 2M
        if "Volume" in large_df.columns:
            large_df["VolumeNumeric"] = large_df["Volume"].apply(
                lambda x: int(str(x).replace(",", "")) if pd.notna(x) else 0
            )
            large_df_filtered = large_df[large_df["VolumeNumeric"] > 2_000_000]
            large_symbols = set(large_df_filtered["Ticker"].tolist())
            print(f"   After volume filter (>2M): {len(large_symbols)} stocks")

        all_symbols.update(large_symbols)

    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch large cap stocks: {e}")

    # Combine results
    final_symbols = sorted(list(all_symbols))

    print("\n" + "-" * 80)
    print(f"📊 Total unique symbols: {len(final_symbols)}")
    print("-" * 80)

    return final_symbols


def compare_with_current_list(new_symbols: list[str]) -> dict:
    """Compare new symbols with current seed list.

    Args:
        new_symbols: New symbols from screener

    Returns:
        Dictionary with comparison statistics
    """
    print("\n" + "=" * 80)
    print("COMPARING WITH CURRENT SEED LIST")
    print("=" * 80)

    try:
        current_symbols = load_seed_list()
        current_set = set(current_symbols)
        new_set = set(new_symbols)

        added = new_set - current_set
        removed = current_set - new_set
        unchanged = current_set & new_set

        print(f"\n📈 Added:     {len(added)} symbols")
        if added:
            print(f"   {', '.join(sorted(list(added))[:20])}")
            if len(added) > 20:
                print(f"   ... and {len(added) - 20} more")

        print(f"\n📉 Removed:   {len(removed)} symbols")
        if removed:
            print(f"   {', '.join(sorted(list(removed))[:20])}")
            if len(removed) > 20:
                print(f"   ... and {len(removed) - 20} more")

        print(f"\n✅ Unchanged: {len(unchanged)} symbols")

        return {
            "current_count": len(current_symbols),
            "new_count": len(new_symbols),
            "added_count": len(added),
            "removed_count": len(removed),
            "unchanged_count": len(unchanged),
            "added": sorted(list(added)),
            "removed": sorted(list(removed)),
        }

    except FileNotFoundError:
        print("\n⚠️  No existing seed list found (this is the first run)")
        return {
            "current_count": 0,
            "new_count": len(new_symbols),
            "added_count": len(new_symbols),
            "removed_count": 0,
            "unchanged_count": 0,
            "added": new_symbols,
            "removed": [],
        }


def main():
    """Main update workflow."""
    print("\n" + "=" * 80)
    print("🔄 SEED LIST UPDATE SCRIPT")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Step 1: Screen stocks
    new_symbols = screen_stocks()

    if not new_symbols:
        print("\n❌ Error: No symbols found. Aborting update.")
        return 1

    # Step 2: Compare with current list
    comparison = compare_with_current_list(new_symbols)

    # Step 3: Confirm update
    print("\n" + "=" * 80)
    print("UPDATE CONFIRMATION")
    print("=" * 80)
    print(f"Current seed list: {comparison['current_count']} symbols")
    print(f"New seed list:     {comparison['new_count']} symbols")
    print(f"Net change:        {comparison['new_count'] - comparison['current_count']:+d} symbols")

    response = input("\n❓ Update seed list? (yes/no): ").strip().lower()

    if response not in ["yes", "y"]:
        print("\n⛔ Update cancelled by user")
        return 0

    # Step 4: Save updated seed list
    print("\n💾 Saving updated seed list...")

    metadata = {
        "description": "High-liquidity US stocks for universe selection",
        "screener": "finviz",
        "filters": "cap_mega (>$200B) + cap_large ($10B-$200B), volume > 2M",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "update_frequency": "biweekly",
        "previous_count": comparison["current_count"],
        "added_count": comparison["added_count"],
        "removed_count": comparison["removed_count"],
    }

    save_seed_list(new_symbols, metadata=metadata)

    print("✅ Seed list updated successfully!")
    print(f"   Location: data/seed_list.json")
    print(f"   Total symbols: {len(new_symbols)}")

    # Step 5: Summary
    print("\n" + "=" * 80)
    print("✅ UPDATE COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
