#!/usr/bin/env python3
"""CLI tool for comparing multiple trading strategies.

This script compares the performance of different strategies side-by-side
and helps identify which approach works best for a given market condition.

Examples:
    # Compare all strategies on AAPL
    python scripts/compare_strategies.py \\
        --symbols AAPL \\
        --start 2023-01-01 --end 2024-01-01

    # Compare specific strategies on multiple stocks
    python scripts/compare_strategies.py \\
        --symbols AAPL MSFT GOOGL \\
        --start 2023-01-01 --end 2024-01-01 \\
        --strategies ma_crossover rsi macd \\
        --output comparison_results.csv
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.strategy.ma_crossover import MACrossoverStrategy
from src.strategy.rsi_strategy import RSIStrategy
from src.strategy.macd_strategy import MACDStrategy
from src.strategy.bollinger_bands_strategy import BollingerBandsStrategy
from src.analysis import StrategyComparator


# Predefined strategy configurations
STRATEGY_CONFIGS = {
    "ma_crossover": {
        "name": "MA Crossover (20/50)",
        "class": MACrossoverStrategy,
        "params": {
            "fast_period": 20,
            "slow_period": 50,
            "min_required_rows": 60,
        },
    },
    "ma_crossover_fast": {
        "name": "MA Crossover (10/30)",
        "class": MACrossoverStrategy,
        "params": {
            "fast_period": 10,
            "slow_period": 30,
            "min_required_rows": 40,
        },
    },
    "ma_crossover_slow": {
        "name": "MA Crossover (50/200)",
        "class": MACrossoverStrategy,
        "params": {
            "fast_period": 50,
            "slow_period": 200,
            "min_required_rows": 210,
        },
    },
    "rsi": {
        "name": "RSI (14, 30/70)",
        "class": RSIStrategy,
        "params": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 30,
        },
    },
    "rsi_aggressive": {
        "name": "RSI (14, 40/60)",
        "class": RSIStrategy,
        "params": {
            "rsi_period": 14,
            "oversold_threshold": 40,
            "overbought_threshold": 60,
            "min_required_rows": 30,
        },
    },
    "macd": {
        "name": "MACD (12/26/9)",
        "class": MACDStrategy,
        "params": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        },
    },
    "bollinger_bands": {
        "name": "Bollinger Bands (20, 2.0)",
        "class": BollingerBandsStrategy,
        "params": {
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 30,
        },
    },
    "bollinger_bands_tight": {
        "name": "Bollinger Bands (20, 1.5)",
        "class": BollingerBandsStrategy,
        "params": {
            "period": 20,
            "num_std": 1.5,
            "min_required_rows": 30,
        },
    },
}


def main():
    """Run strategy comparison."""
    parser = argparse.ArgumentParser(
        description="Compare performance of multiple trading strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=list(STRATEGY_CONFIGS.keys()) + ["all"],
        default=["all"],
        help="Strategies to compare (default: all)",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["AAPL"],
        help="Stock symbols to backtest on (default: AAPL)",
    )

    parser.add_argument(
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end",
        required=True,
        help="End date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial capital (default: 100000)",
    )

    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly", "monthly"],
        default="weekly",
        help="Rebalancing frequency (default: weekly)",
    )

    parser.add_argument(
        "--output",
        help="Optional CSV file to save results",
    )

    args = parser.parse_args()

    # Determine which strategies to run
    if "all" in args.strategies:
        strategy_keys = list(STRATEGY_CONFIGS.keys())
    else:
        strategy_keys = args.strategies

    # Build strategy list
    strategies = []
    for key in strategy_keys:
        config = STRATEGY_CONFIGS[key]
        strategy_instance = config["class"](config["params"])
        strategies.append((config["name"], strategy_instance))

    print(f"\n📊 Comparing {len(strategies)} strategies")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Period: {args.start} to {args.end}\n")

    # Create comparator and run comparison
    comparator = StrategyComparator(strategies)

    results = comparator.compare(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        rebalance_frequency=args.frequency,
    )

    # Print summary
    comparator.print_summary()

    # Export if requested
    if args.output:
        comparator.export_to_csv(args.output)
        print(f"📁 Results exported to: {args.output}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
