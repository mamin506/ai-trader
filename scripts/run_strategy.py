#!/usr/bin/env python3
"""CLI tool for running a single trading strategy.

This script backtests a trading strategy on specified symbols and displays
performance metrics.

Examples:
    # Run MA Crossover on AAPL
    python scripts/run_strategy.py \\
        --strategy ma_crossover \\
        --symbols AAPL \\
        --start 2023-01-01 --end 2024-01-01

    # Run RSI strategy on universe
    python scripts/run_strategy.py \\
        --strategy rsi \\
        --universe liquid_50 \\
        --start 2023-01-01 --end 2024-01-01

    # Run with custom parameters
    python scripts/run_strategy.py \\
        --strategy ma_crossover \\
        --symbols AAPL MSFT GOOGL \\
        --start 2023-01-01 --end 2024-01-01 \\
        --capital 50000 \\
        --frequency daily
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.strategy.ma_crossover import MACrossoverStrategy
from src.strategy.rsi_strategy import RSIStrategy
from src.strategy.macd_strategy import MACDStrategy
from src.strategy.bollinger_bands_strategy import BollingerBandsStrategy
from src.api.universe_api import UniverseAPI
from src.api.strategy_api import StrategyAPI


# Available strategies with default parameters
STRATEGIES = {
    "ma_crossover": {
        "name": "MA Crossover",
        "class": MACrossoverStrategy,
        "params": {
            "fast_period": 20,
            "slow_period": 50,
            "min_required_rows": 60,
        },
        "description": "Moving Average Crossover (20/50)",
    },
    "ma_crossover_fast": {
        "name": "MA Crossover Fast",
        "class": MACrossoverStrategy,
        "params": {
            "fast_period": 10,
            "slow_period": 30,
            "min_required_rows": 40,
        },
        "description": "Moving Average Crossover (10/30)",
    },
    "ma_crossover_slow": {
        "name": "MA Crossover Slow",
        "class": MACrossoverStrategy,
        "params": {
            "fast_period": 50,
            "slow_period": 200,
            "min_required_rows": 210,
        },
        "description": "Moving Average Crossover (50/200)",
    },
    "rsi": {
        "name": "RSI",
        "class": RSIStrategy,
        "params": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_required_rows": 30,
        },
        "description": "RSI Strategy (14, 30/70)",
    },
    "rsi_aggressive": {
        "name": "RSI Aggressive",
        "class": RSIStrategy,
        "params": {
            "rsi_period": 14,
            "oversold_threshold": 40,
            "overbought_threshold": 60,
            "min_required_rows": 30,
        },
        "description": "RSI Strategy (14, 40/60)",
    },
    "macd": {
        "name": "MACD",
        "class": MACDStrategy,
        "params": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_required_rows": 50,
        },
        "description": "MACD Strategy (12/26/9)",
    },
    "bollinger_bands": {
        "name": "Bollinger Bands",
        "class": BollingerBandsStrategy,
        "params": {
            "period": 20,
            "num_std": 2.0,
            "min_required_rows": 30,
        },
        "description": "Bollinger Bands (20, 2.0)",
    },
    "bollinger_bands_tight": {
        "name": "Bollinger Bands Tight",
        "class": BollingerBandsStrategy,
        "params": {
            "period": 20,
            "num_std": 1.5,
            "min_required_rows": 30,
        },
        "description": "Bollinger Bands (20, 1.5)",
    },
}


def list_strategies():
    """Print available strategies."""
    print("\n" + "=" * 70)
    print("AVAILABLE STRATEGIES")
    print("=" * 70)

    for key, config in STRATEGIES.items():
        print(f"\n{key:25s} - {config['description']}")

    print("\n" + "=" * 70)
    print()


def main():
    """Run strategy backtest."""
    parser = argparse.ArgumentParser(
        description="Run a single trading strategy backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available strategies and exit",
    )

    parser.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        help="Strategy to run",
    )

    # Symbol selection (mutually exclusive)
    symbol_group = parser.add_mutually_exclusive_group()
    symbol_group.add_argument(
        "--symbols",
        nargs="+",
        help="Stock symbols to backtest on (e.g., AAPL MSFT GOOGL)",
    )
    symbol_group.add_argument(
        "--universe",
        help="Load symbols from saved universe (e.g., liquid_50)",
    )

    parser.add_argument(
        "--start",
        help="Start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end",
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

    args = parser.parse_args()

    # List strategies if requested
    if args.list:
        list_strategies()
        return 0

    # Validate required arguments
    if not args.strategy:
        parser.error("--strategy is required (or use --list to see available strategies)")

    if not args.symbols and not args.universe:
        parser.error("either --symbols or --universe is required")

    if not args.start or not args.end:
        parser.error("both --start and --end are required")

    # Get symbols
    if args.universe:
        print(f"Loading universe '{args.universe}'...")
        try:
            universe_api = UniverseAPI()
            symbols = universe_api.load_universe(args.universe)
            print(f"✓ Loaded {len(symbols)} symbols from universe\n")
        except Exception as e:
            print(f"✗ Error loading universe: {e}")
            return 1
    else:
        symbols = args.symbols

    # Create strategy instance
    strategy_config = STRATEGIES[args.strategy]
    strategy = strategy_config["class"](strategy_config["params"])

    # Print configuration
    print("=" * 70)
    print("STRATEGY BACKTEST")
    print("=" * 70)
    print(f"Strategy:        {strategy_config['description']}")
    print(f"Symbols:         {', '.join(symbols)}")
    print(f"Period:          {args.start} to {args.end}")
    print(f"Initial Capital: ${args.capital:,.2f}")
    print(f"Frequency:       {args.frequency}")
    print("=" * 70)
    print()

    # Run backtest
    try:
        print("Running backtest...")
        print()

        strategy_api = StrategyAPI()

        results = strategy_api.backtest(
            strategy=strategy,
            symbols=symbols,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            rebalance_frequency=args.frequency,
        )

        # Display results
        print("=" * 70)
        print("BACKTEST RESULTS")
        print("=" * 70)
        print()

        # Performance metrics
        print("Performance Metrics:")
        print(f"  Total Return:      {results['total_return']:>10.2%}")
        print(f"  Annualized Return: {results['annualized_return']:>10.2%}")
        print(f"  Sharpe Ratio:      {results['sharpe_ratio']:>10.2f}")
        print(f"  Max Drawdown:      {results['max_drawdown']:>10.2%}")
        print(f"  Win Rate:          {results['win_rate']:>10.2%}")
        print()

        # Trading statistics
        print("Trading Statistics:")
        print(f"  Total Trades:      {results['total_trades']:>10d}")
        print(f"  Winning Trades:    {results['winning_trades']:>10d}")
        print(f"  Losing Trades:     {results['losing_trades']:>10d}")
        print()

        # Final values
        print("Final Portfolio:")
        print(f"  Starting Capital:  ${results['starting_capital']:>12,.2f}")
        print(f"  Ending Value:      ${results['ending_value']:>12,.2f}")
        print(f"  Profit/Loss:       ${results['total_pnl']:>12,.2f}")
        print()

        print("=" * 70)
        print()

        # Success message
        print(f"✓ Backtest completed successfully")
        print()

        return 0

    except Exception as e:
        print(f"✗ Error running backtest: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
