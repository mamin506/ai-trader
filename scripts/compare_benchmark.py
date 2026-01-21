#!/usr/bin/env python3
"""Compare strategy performance against benchmark.

This script runs your strategy and compares it to a buy-and-hold benchmark (SPY).

Examples:
    # Compare MA Crossover vs SPY
    python scripts/compare_benchmark.py AAPL MSFT GOOGL \\
        --start 2024-01-01 --end 2024-12-31

    # Use custom benchmark (QQQ for tech stocks)
    python scripts/compare_benchmark.py AAPL MSFT \\
        --benchmark QQQ --start 2024-01-01

    # Custom strategy parameters
    python scripts/compare_benchmark.py AAPL MSFT \\
        -p fast_period=10 -p slow_period=30
"""

import sys
from datetime import datetime, timedelta
from typing import Dict, Optional

import click

sys.path.append(".")

from src.api.backtest_api import BacktestAPI
from src.strategy.ma_crossover import MACrossoverStrategy


def parse_params(param_list: tuple) -> Dict:
    """Parse parameter strings into a dictionary."""
    params = {}
    for param in param_list:
        if "=" not in param:
            continue
        key, value = param.split("=", 1)
        try:
            params[key] = int(value)
        except ValueError:
            try:
                params[key] = float(value)
            except ValueError:
                params[key] = value
    return params


def calculate_comparison_metrics(strategy_result, benchmark_result) -> Dict[str, float]:
    """Calculate comparison metrics between strategy and benchmark.

    Args:
        strategy_result: BacktestResult object
        benchmark_result: Dict from calculate_buy_and_hold_return
    """
    # Handle None values for Sharpe ratios
    strategy_sharpe = strategy_result.sharpe_ratio if strategy_result.sharpe_ratio is not None else 0.0
    benchmark_sharpe = benchmark_result['sharpe_ratio'] if benchmark_result['sharpe_ratio'] is not None else 0.0

    return {
        'alpha': strategy_result.annualized_return - benchmark_result['annualized_return'],
        'alpha_pct': (strategy_result.annualized_return - benchmark_result['annualized_return']) * 100,
        'outperformance': (strategy_result.total_return - benchmark_result['total_return']) * 100,
        'sharpe_advantage': strategy_sharpe - benchmark_sharpe,
        'drawdown_ratio': strategy_result.max_drawdown / benchmark_result['max_drawdown'] if benchmark_result['max_drawdown'] > 0 else 0,
        'trade_efficiency': strategy_result.win_rate - 0,  # Buy-and-hold has no trades
    }


def format_verdict(metrics: Dict[str, float], strategy_result, benchmark_result) -> str:
    """Generate a verdict on strategy effectiveness."""
    lines = []

    # Calculate score
    score = 0
    reasons = []

    # Alpha (most important)
    if metrics['alpha_pct'] > 5:
        score += 3
        reasons.append(f"✅ Excellent alpha: {metrics['alpha_pct']:.2f}%")
    elif metrics['alpha_pct'] > 2:
        score += 2
        reasons.append(f"✅ Good alpha: {metrics['alpha_pct']:.2f}%")
    elif metrics['alpha_pct'] > 0:
        score += 1
        reasons.append(f"⚠️ Positive alpha: {metrics['alpha_pct']:.2f}%")
    else:
        score -= 2
        reasons.append(f"❌ Negative alpha: {metrics['alpha_pct']:.2f}%")

    # Sharpe Ratio
    if strategy_result.sharpe_ratio and strategy_result.sharpe_ratio > 2.0:
        score += 2
        reasons.append(f"✅ Excellent Sharpe: {strategy_result.sharpe_ratio:.2f}")
    elif strategy_result.sharpe_ratio and strategy_result.sharpe_ratio > 1.0:
        score += 1
        reasons.append(f"✅ Good Sharpe: {strategy_result.sharpe_ratio:.2f}")
    elif strategy_result.sharpe_ratio and strategy_result.sharpe_ratio > 0.5:
        reasons.append(f"⚠️ Marginal Sharpe: {strategy_result.sharpe_ratio:.2f}")
    else:
        score -= 1
        sharpe_val = strategy_result.sharpe_ratio if strategy_result.sharpe_ratio else 0
        reasons.append(f"❌ Low Sharpe: {sharpe_val:.2f}")

    # Max Drawdown
    if strategy_result.max_drawdown < 0.10:
        score += 1
        reasons.append(f"✅ Low drawdown: {strategy_result.max_drawdown*100:.2f}%")
    elif strategy_result.max_drawdown < 0.20:
        reasons.append(f"✅ Acceptable drawdown: {strategy_result.max_drawdown*100:.2f}%")
    elif strategy_result.max_drawdown < 0.30:
        reasons.append(f"⚠️ High drawdown: {strategy_result.max_drawdown*100:.2f}%")
    else:
        score -= 1
        reasons.append(f"❌ Excessive drawdown: {strategy_result.max_drawdown*100:.2f}%")

    # Generate verdict
    lines.append("=" * 70)
    lines.append("STRATEGY EVALUATION VERDICT")
    lines.append("=" * 70)

    if score >= 5:
        lines.append("🏆 EXCELLENT STRATEGY - Ready for live trading consideration")
    elif score >= 3:
        lines.append("✅ EFFECTIVE STRATEGY - Beats benchmark with good risk profile")
    elif score >= 1:
        lines.append("⚠️ MARGINAL STRATEGY - Needs improvement before live trading")
    else:
        lines.append("❌ INEFFECTIVE STRATEGY - Does not meet trading criteria")

    lines.append("")
    lines.append("Reasons:")
    for reason in reasons:
        lines.append(f"  {reason}")

    lines.append("")
    lines.append("Recommendation:")
    if score >= 5:
        lines.append("  • Consider paper trading to validate")
        lines.append("  • Test on out-of-sample data")
        lines.append("  • Proceed cautiously to live trading")
    elif score >= 3:
        lines.append("  • Strategy shows promise")
        lines.append("  • Consider parameter optimization")
        lines.append("  • Test on different time periods")
    elif score >= 1:
        lines.append("  • Requires significant improvement")
        lines.append("  • Explore different strategies or parameters")
        lines.append("  • Not recommended for live trading")
    else:
        lines.append("  • Strategy underperforms benchmark")
        lines.append("  • Better to buy-and-hold the benchmark")
        lines.append("  • Do not trade this strategy")

    lines.append("=" * 70)

    return "\n".join(lines)


@click.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--benchmark", default="SPY", help="Benchmark symbol (default: SPY)")
@click.option("--start", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end", type=str, help="End date (YYYY-MM-DD)")
@click.option("--capital", type=float, default=100000.0, help="Initial capital")
@click.option("--param", "-p", multiple=True, help="Strategy parameter (key=value)")
@click.option("--strategy", default="ma-crossover", help="Strategy name")
def compare(
    symbols: tuple,
    benchmark: str,
    start: Optional[str],
    end: Optional[str],
    capital: float,
    param: tuple,
    strategy: str,
):
    """Compare strategy performance against benchmark.

    SYMBOLS: Stock ticker symbols for the strategy

    The script will:
    1. Run your strategy on the given symbols
    2. Run buy-and-hold on the benchmark (default: SPY)
    3. Calculate comparison metrics (alpha, Sharpe advantage, etc.)
    4. Provide a verdict on strategy effectiveness

    Examples:

        \b
        # Compare to SPY
        python scripts/compare_benchmark.py AAPL MSFT GOOGL

        \b
        # Use QQQ as benchmark (for tech stocks)
        python scripts/compare_benchmark.py AAPL MSFT --benchmark QQQ

        \b
        # Custom MA periods
        python scripts/compare_benchmark.py AAPL MSFT -p fast_period=10 -p slow_period=30
    """
    # Set default date range
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Header
    click.echo("=" * 70)
    click.echo("STRATEGY vs BENCHMARK COMPARISON")
    click.echo("=" * 70)
    click.echo(f"Strategy Symbols: {', '.join(symbols)}")
    click.echo(f"Benchmark:        {benchmark}")
    click.echo(f"Period:           {start} to {end}")
    click.echo(f"Capital:          ${capital:,.2f}")

    strategy_params = parse_params(param)
    if strategy_params:
        click.echo(f"Parameters:       {strategy_params}")

    click.echo("=" * 70)
    click.echo()

    try:
        api = BacktestAPI()

        # Run strategy backtest
        click.echo(f"Running strategy on {', '.join(symbols)}...")

        if strategy == "ma-crossover":
            default_params = {"fast_period": 50, "slow_period": 200}
            default_params.update(strategy_params)

            strategy_result = api.run_ma_crossover(
                symbols=list(symbols),
                start_date=start,
                end_date=end,
                fast_period=default_params["fast_period"],
                slow_period=default_params["slow_period"],
                initial_cash=capital,
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        click.echo("✓ Strategy backtest complete")
        click.echo()

        # Run benchmark (true buy-and-hold)
        click.echo(f"Running buy-and-hold benchmark ({benchmark})...")

        # Calculate true buy-and-hold return
        benchmark_result = api.calculate_buy_and_hold_return(
            symbol=benchmark,
            start_date=start,
            end_date=end,
            initial_cash=capital,
        )

        click.echo(f"✓ Bought {benchmark_result['shares']:.2f} shares @ ${benchmark_result['first_price']:.2f}")
        click.echo(f"✓ Final price: ${benchmark_result['last_price']:.2f}")
        click.echo("✓ Benchmark calculation complete")
        click.echo()

        # Display individual results
        click.echo("=" * 70)
        click.echo("STRATEGY RESULTS")
        click.echo("=" * 70)
        click.echo(f"Total Return:       {strategy_result.total_return_pct:>12.2f}%")
        click.echo(f"Annualized Return:  {strategy_result.annualized_return * 100:>12.2f}%")
        click.echo(f"Sharpe Ratio:       {strategy_result.sharpe_ratio:>12.2f}" if strategy_result.sharpe_ratio else "Sharpe Ratio:              N/A")
        click.echo(f"Max Drawdown:       {strategy_result.max_drawdown * 100:>12.2f}%")
        click.echo(f"Win Rate:           {strategy_result.win_rate * 100:>12.2f}%")
        click.echo(f"Number of Trades:   {strategy_result.num_trades:>12}")
        click.echo()

        click.echo("=" * 70)
        click.echo(f"BENCHMARK RESULTS (Buy & Hold {benchmark})")
        click.echo("=" * 70)
        click.echo(f"Initial Price:      ${benchmark_result['first_price']:>12.2f}")
        click.echo(f"Final Price:        ${benchmark_result['last_price']:>12.2f}")
        click.echo(f"Shares Bought:      {benchmark_result['shares']:>12.2f}")
        click.echo(f"Total Return:       {benchmark_result['total_return_pct']:>12.2f}%")
        click.echo(f"Annualized Return:  {benchmark_result['annualized_return'] * 100:>12.2f}%")
        click.echo(f"Sharpe Ratio:       {benchmark_result['sharpe_ratio']:>12.2f}" if benchmark_result['sharpe_ratio'] else "Sharpe Ratio:              N/A")
        click.echo(f"Max Drawdown:       {benchmark_result['max_drawdown'] * 100:>12.2f}%")
        click.echo()

        # Calculate comparison metrics
        comparison = calculate_comparison_metrics(strategy_result, benchmark_result)

        # Display comparison
        click.echo("=" * 70)
        click.echo("COMPARATIVE ANALYSIS")
        click.echo("=" * 70)
        click.echo(f"Alpha:              {comparison['alpha_pct']:>12.2f}%")
        click.echo(f"Outperformance:     {comparison['outperformance']:>12.2f}%")
        click.echo(f"Sharpe Advantage:   {comparison['sharpe_advantage']:>12.2f}")
        click.echo(f"Drawdown Ratio:     {comparison['drawdown_ratio']:>12.2f}x")
        click.echo()

        # Display verdict
        verdict = format_verdict(comparison, strategy_result, benchmark_result)
        click.echo(verdict)

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    compare()
