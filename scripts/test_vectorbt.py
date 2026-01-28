#!/usr/bin/env python3
"""Quick test script for VectorBT integration.

This script demonstrates the VectorBT API functionality and verifies
the installation is working correctly.
"""

import sys

sys.path.append(".")

from datetime import datetime

from src.api.vectorbt_api import VectorBTAPI
from src.strategy.ma_crossover import MACrossoverStrategy


def test_quick_backtest():
    """Test basic VectorBT backtesting."""
    print("=" * 70)
    print("TEST 1: Quick Backtest")
    print("=" * 70)

    # Create API and strategy
    api = VectorBTAPI()
    strategy = MACrossoverStrategy({"fast_period": 20, "slow_period": 50})

    # Run quick backtest (use 2024 Q1 data)
    print("\nRunning VectorBT backtest on AAPL (2024 Q1)...")
    result = api.quick_backtest(
        strategy=strategy, symbol="AAPL", start_date="2024-01-02", end_date="2024-03-29"
    )

    # Display results
    print("\nResults:")
    print(f"  Total Return:      {result.total_return:>10.2%}")
    print(f"  Annualized Return: {result.annualized_return:>10.2%}")
    print(f"  Sharpe Ratio:      {result.sharpe_ratio:>10.2f}")
    print(f"  Max Drawdown:      {result.max_drawdown:>10.2%}")
    print(f"  Win Rate:          {result.win_rate:>10.2%}")
    print(f"  Number of Trades:  {result.num_trades:>10}")

    print("\n✅ Quick backtest test passed!")
    return result


def test_parameter_optimization():
    """Test parameter optimization."""
    print("\n" + "=" * 70)
    print("TEST 2: Parameter Optimization")
    print("=" * 70)

    # Create API
    api = VectorBTAPI()

    # Define parameter grid
    param_grid = {
        "fast_period": [10, 20, 30],
        "slow_period": [50, 100],
    }

    total_combinations = 3 * 2
    print(f"\nOptimizing {total_combinations} parameter combinations...")
    print("Param grid:")
    print(f"  fast_period: {param_grid['fast_period']}")
    print(f"  slow_period: {param_grid['slow_period']}")

    # Run optimization (use 2024 Q1 data)
    results = api.optimize_strategy(
        strategy_class=MACrossoverStrategy,
        symbol="AAPL",
        param_grid=param_grid,
        start_date="2024-01-02",
        end_date="2024-03-29",
        metric="sharpe_ratio",
        top_n=3,
    )

    # Display top 3 results
    print("\nTop 3 parameter combinations:")
    print(results[["fast_period", "slow_period", "sharpe_ratio", "total_return"]].to_string(index=False))

    print("\n✅ Parameter optimization test passed!")
    return results


def test_batch_backtest():
    """Test batch backtesting across multiple symbols."""
    print("\n" + "=" * 70)
    print("TEST 3: Batch Backtest")
    print("=" * 70)

    # Create API and strategy
    api = VectorBTAPI()
    strategy = MACrossoverStrategy({"fast_period": 20, "slow_period": 50})

    # Test on multiple symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]
    print(f"\nRunning batch backtest on {len(symbols)} symbols...")
    print(f"Symbols: {', '.join(symbols)}")

    results = api.batch_backtest(
        strategy=strategy, symbols=symbols, start_date="2024-01-02", end_date="2024-03-29"
    )

    # Sort by Sharpe ratio
    results = results.sort_values("sharpe_ratio", ascending=False)

    # Display results
    print("\nResults (sorted by Sharpe ratio):")
    print(results[["symbol", "total_return", "sharpe_ratio", "max_drawdown"]].to_string(index=False))

    print("\n✅ Batch backtest test passed!")
    return results


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("VECTORBT INTEGRATION TEST SUITE")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Run tests
        test_quick_backtest()
        test_parameter_optimization()
        test_batch_backtest()

        # Summary
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED! ✅")
        print("=" * 70)
        print("\nVectorBT integration is working correctly.")
        print("You can now use VectorBTAPI for fast backtesting and optimization!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
