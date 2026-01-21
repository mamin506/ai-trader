# Strategy Evaluation Guide

## How to Know If a Strategy Works?

This guide explains how to evaluate whether your trading strategy is effective.

## Quick Answer

A strategy is considered **effective** if it meets these criteria:

1. **Beats the Benchmark**: Returns > SPY (S&P 500) returns
2. **Good Risk-Adjusted Returns**: Sharpe Ratio > 1.0
3. **Acceptable Drawdown**: Max Drawdown < 20%
4. **Consistent Performance**: Positive alpha over multiple time periods

## Evaluation Framework

### 1. Absolute Performance Metrics

These measure raw performance without comparison:

| Metric | Formula | Good Value | Excellent Value |
|--------|---------|------------|-----------------|
| **Total Return** | (Final - Initial) / Initial | > 10% annual | > 20% annual |
| **Annualized Return** | CAGR over period | > 10% | > 20% |
| **Max Drawdown** | Largest peak-to-trough drop | < 20% | < 10% |
| **Win Rate** | Winning trades / Total trades | > 40% | > 55% |

### 2. Risk-Adjusted Performance Metrics

These account for risk taken to achieve returns:

| Metric | Formula | Interpretation | Good Value |
|--------|---------|----------------|------------|
| **Sharpe Ratio** | (Return - Risk-free) / StdDev | Return per unit of risk | > 1.0 |
| **Sortino Ratio** | (Return - Risk-free) / Downside StdDev | Penalizes downside volatility only | > 1.5 |
| **Calmar Ratio** | Annualized Return / Max Drawdown | Return per unit of max loss | > 2.0 |

**Current Implementation**: Our `BacktestResult` includes Sharpe Ratio. We recommend adding Sortino and Calmar in Phase 2.

### 3. Benchmark Comparison (Most Important!)

Compare your strategy against a passive buy-and-hold benchmark:

| Metric | Formula | Interpretation | Target |
|--------|---------|----------------|--------|
| **Alpha** | Strategy Return - Benchmark Return | Excess return | > 0% |
| **Beta** | Correlation with benchmark | Market sensitivity | 0.5-1.5 |
| **Information Ratio** | Alpha / Tracking Error | Risk-adjusted alpha | > 0.5 |

**Recommended Benchmarks**:
- **General US Stocks**: SPY (S&P 500)
- **Tech-Heavy**: QQQ (Nasdaq-100)
- **Small Cap**: IWM (Russell 2000)

### 4. Industry Standards

#### Individual Trader Standards (Realistic)
```
✅ Sharpe Ratio > 0.5        (Better than random)
✅ Alpha > 0%                 (Beats benchmark)
✅ Max Drawdown < 30%         (Survivable losses)
✅ Annualized Return > 8%     (Beats inflation + bonds)
```

#### Quantitative Fund Standards (Aspirational)
```
🏆 Sharpe Ratio > 2.0
🏆 Alpha > 5% annualized
🏆 Max Drawdown < 10%
🏆 Information Ratio > 1.0
```

## Practical Evaluation Workflow

### Step 1: Run Backtest with Benchmark

```python
from src.api.backtest_api import BacktestAPI

api = BacktestAPI()

# Your strategy
strategy_result = api.run_ma_crossover(
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2024-01-01',
    end_date='2024-12-31',
    fast_period=50,
    slow_period=200,
    initial_cash=100000
)

# Benchmark (Buy-and-hold SPY)
benchmark_result = api.run_ma_crossover(
    symbols=['SPY'],
    start_date='2024-01-01',
    end_date='2024-12-31',
    fast_period=1,      # No crossover, always hold
    slow_period=2,
    initial_cash=100000
)
```

### Step 2: Calculate Key Metrics

```python
# Alpha (excess return)
alpha = strategy_result.annualized_return - benchmark_result.annualized_return
alpha_pct = alpha * 100

# Relative Sharpe
sharpe_diff = strategy_result.sharpe_ratio - benchmark_result.sharpe_ratio

# Outperformance
outperformance = (strategy_result.total_return - benchmark_result.total_return) * 100

print(f"Alpha: {alpha_pct:.2f}%")
print(f"Sharpe Advantage: {sharpe_diff:.2f}")
print(f"Outperformance: {outperformance:.2f}%")
```

### Step 3: Decision Matrix

```
IF alpha > 0% AND sharpe_ratio > 1.0 AND max_drawdown < 20%:
    ✅ Strategy is EFFECTIVE - Consider live trading

ELIF alpha > 0% AND sharpe_ratio > 0.5:
    ⚠️ Strategy is MARGINAL - Needs improvement

ELIF alpha <= 0%:
    ❌ Strategy UNDERPERFORMS - Don't trade

ELSE:
    ⚠️ Strategy is HIGH RISK - Evaluate risk tolerance
```

## Common Pitfalls

### 1. Overfitting (Curve Fitting)
**Problem**: Strategy works on backtest but fails in live trading.

**Solution**:
- Test on **out-of-sample data** (different time period)
- Use **walk-forward analysis**
- Avoid over-optimization (too many parameters)

### 2. Survivorship Bias
**Problem**: Backtesting only symbols that survived (not delisted).

**Solution**:
- Include delisted stocks in historical data
- Use broad market indices for benchmark

### 3. Look-Ahead Bias
**Problem**: Using future information in past decisions.

**Solution**:
- Ensure signals only use past data
- Validate data alignment in backtests

### 4. Transaction Costs
**Problem**: Ignoring slippage and commissions.

**Solution**: Our backtest includes configurable slippage (0.1%) and commissions.

## Recommended Evaluation for Your Project

For your **personal AI Trader project**, I recommend this evaluation framework:

### Minimum Viable Strategy
```python
# A strategy is "good enough to trade" if:
requirements = {
    'alpha': > 2%,                    # Beats SPY by 2% annually
    'sharpe_ratio': > 1.0,            # Decent risk-adjusted return
    'max_drawdown': < 25%,            # Tolerable max loss
    'win_rate': > 40%,                # Not too many losing trades
    'num_trades': > 20,               # Enough statistical significance
}
```

### Testing Protocol
1. **Backtest Period**: Minimum 2 years of data
2. **Out-of-Sample Test**: Reserve last 6 months for validation
3. **Benchmark**: Always compare to SPY
4. **Parameter Sensitivity**: Test with ±20% parameter variation
5. **Multiple Symbols**: Test on at least 5-10 different stocks

### Red Flags (Don't Trade!)
```
❌ Sharpe Ratio < 0.5              (Barely better than random)
❌ Max Drawdown > 40%              (Catastrophic risk)
❌ Win Rate < 30%                  (Too many losses)
❌ Alpha < -2%                     (Significantly underperforms)
❌ Only 1-5 trades total           (Not statistically significant)
```

## Next Steps for Your Project

### Phase 1.5: Add Benchmark Comparison
Implement these enhancements to `BacktestAPI`:

```python
def compare_to_benchmark(
    strategy_result: BacktestResult,
    benchmark_result: BacktestResult
) -> Dict[str, float]:
    """Compare strategy to benchmark."""
    return {
        'alpha': strategy_result.annualized_return - benchmark_result.annualized_return,
        'outperformance_pct': (strategy_result.total_return - benchmark_result.total_return) * 100,
        'sharpe_advantage': strategy_result.sharpe_ratio - benchmark_result.sharpe_ratio,
        'drawdown_ratio': strategy_result.max_drawdown / benchmark_result.max_drawdown,
    }
```

### Phase 2: Advanced Metrics
Add these metrics to `BacktestResult`:
- Sortino Ratio (downside deviation)
- Calmar Ratio (return / max drawdown)
- Beta (market correlation)
- Information Ratio (risk-adjusted alpha)

## References

- **Academic**: Sharpe, W. F. (1994). "The Sharpe Ratio"
- **Industry**: QuantStats library (comprehensive performance metrics)
- **Books**:
  - "Algorithmic Trading" by Ernest Chan
  - "Advances in Financial Machine Learning" by Marcos López de Prado

## Summary

**For your personal project, a strategy is effective if:**

1. ✅ **Alpha > 0%**: Beats SPY
2. ✅ **Sharpe > 1.0**: Good risk-adjusted returns
3. ✅ **Max DD < 20%**: Acceptable risk
4. ✅ **Consistent**: Works across different time periods

**The single most important metric**: **Alpha** (beating the benchmark)

If your strategy can't beat SPY, you're better off just buying SPY!
