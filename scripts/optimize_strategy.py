#!/usr/bin/env python3
"""CLI tool for optimizing strategy parameters using grid search.

This script helps find optimal parameters for trading strategies by testing
multiple parameter combinations and comparing their performance.

Examples:
    # Optimize MA Crossover strategy
    python scripts/optimize_strategy.py ma_crossover \\
        --symbols AAPL MSFT GOOGL \\
        --start 2023-01-01 --end 2024-01-01 \\
        --metric sharpe_ratio

    # Optimize RSI strategy with custom grid
    python scripts/optimize_strategy.py rsi \\
        --symbols AAPL \\
        --start 2023-01-01 --end 2024-01-01 \\
        --metric total_return
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
from src.optimization import GridSearchOptimizer


# Predefined parameter grids for each strategy
PARAM_GRIDS = {
    "ma_crossover": {
        "param_grid": {
            "fast_period": [10, 20, 30],
            "slow_period": [50, 100, 200],
        },
        "fixed_params": {"min_required_rows": 50},
        "strategy_class": MACrossoverStrategy,
    },
    "rsi": {
        "param_grid": {
            "rsi_period": [7, 14, 21],
            "oversold_threshold": [20, 30, 40],
            "overbought_threshold": [60, 70, 80],
        },
        "fixed_params": {"min_required_rows": 30},
        "strategy_class": RSIStrategy,
    },
    "macd": {
        "param_grid": {
            "fast_period": [8, 12, 16],
            "slow_period": [20, 26, 32],
            "signal_period": [7, 9, 11],
        },
        "fixed_params": {"min_required_rows": 50},
        "strategy_class": MACDStrategy,
    },
    "bollinger_bands": {
        "param_grid": {
            "period": [10, 20, 30],
            "num_std": [1.5, 2.0, 2.5, 3.0],
        },
        "fixed_params": {"min_required_rows": 35},
        "strategy_class": BollingerBandsStrategy,
    },
}


def main():
    """Run strategy parameter optimization."""
    parser = argparse.ArgumentParser(
        description="Optimize trading strategy parameters using grid search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "strategy",
        choices=list(PARAM_GRIDS.keys()),
        help="Strategy to optimize",
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
        "--metric",
        choices=["sharpe_ratio", "total_return", "max_drawdown"],
        default="sharpe_ratio",
        help="Metric to optimize (default: sharpe_ratio)",
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

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Get strategy configuration
    config = PARAM_GRIDS[args.strategy]

    # Create optimizer
    optimizer = GridSearchOptimizer(
        strategy_class=config["strategy_class"],
        param_grid=config["param_grid"],
        fixed_params=config["fixed_params"],
    )

    # Run optimization
    best_params, results_df = optimizer.optimize(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end,
        metric=args.metric,
        initial_capital=args.capital,
        rebalance_frequency=args.frequency,
        verbose=not args.quiet,
    )

    # Save results if requested
    if args.output:
        results_df.to_csv(args.output, index=False)
        print(f"\n📁 Results saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
