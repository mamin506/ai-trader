# Strategy Layer Design

**Status**: ✅ Decided (2026-01-17)

## Overview

The Strategy Layer is responsible for analyzing market data and generating trading signals. It operates on data provided by the Data Layer for symbols selected by the Universe Selection layer, and outputs directional signals with confidence levels for the Portfolio Management Layer to consume.

## Core Responsibilities

1. **Monitor Universe of Symbols**: Analyze symbols selected by the Universe Selection layer
2. **Calculate Technical Indicators**: Compute indicators (MA, RSI, MACD, etc.) using TA-Lib
3. **Generate Trading Signals**: Output buy/sell/hold signals with strength/confidence scores
4. **Maintain Independence**: Each strategy analyzes securities independently without knowledge of portfolio allocation

**What Strategy Layer Does NOT Do**:
- ❌ Decide position sizes or capital allocation (Portfolio Management Layer's job)
- ❌ Enforce risk limits (Risk Management Layer's job)
- ❌ Execute orders (Execution Layer's job)

## Trading Framework Selection

### Framework Comparison

We evaluated different quantitative trading approaches suitable for individual traders:

| Framework Type | Timeframe | Capital Requirement | Time Investment | Suitable for Personal Bot |
|---------------|-----------|---------------------|-----------------|---------------------------|
| **High-Frequency Trading (HFT)** | Microseconds-Seconds | Very High | Very High | ❌ Requires professional infrastructure |
| **Intraday Trading** | Minutes-Hours | Medium | High (requires monitoring) | ⚠️ Suitable for full-time traders |
| **Swing Trading** | Days-Weeks | Medium | Medium | ✅ Good for part-time |
| **Position Trading** | Weeks-Months | Medium | Low | ✅✅ Excellent for part-time |
| **Single-Asset Strategy** | Varies | Low | Low | ⚠️ High concentration risk |
| **Multi-Asset Portfolio** | Varies | Medium | Low-Medium | ✅✅ Risk-diversified |

### Strategy Classification by Logic

**1. Trend Following**
- Philosophy: Trends persist once established
- Examples: Moving average crossover, Donchian breakout, MACD
- Pros: Captures large moves, simple logic
- Cons: Poor performance in ranging markets, larger drawdowns

**2. Mean Reversion**
- Philosophy: Prices revert to mean after deviation
- Examples: Bollinger Bands, RSI overbought/oversold, pairs trading
- Pros: High win rate, effective in ranging markets
- Cons: Consecutive losses in trending markets

**3. Statistical Arbitrage**
- Philosophy: Exploit statistical pricing relationships
- Examples: Pairs trading, ETF arbitrage, futures-spot arbitrage
- Pros: Market-neutral, lower risk
- Cons: Requires complex modeling, opportunities diminishing

**4. Multi-Factor / Factor-Based**
- Philosophy: Select and weight securities using multiple factors
- Common Factors: Value (P/E, P/B), Momentum (past returns), Quality (ROE), Size (market cap)
- Pros: Strong academic backing, explainable
- Cons: Requires fundamental data, lower turnover

**5. Portfolio-Based Strategies**
- Philosophy: Risk reduction through diversification
- Approaches: Equal weighting, Risk Parity, Markowitz optimization, Black-Litterman
- Pros: Systematic risk management
- Cons: Requires multiple positions, higher capital requirement

## Selected Framework: Multi-Factor Portfolio Strategy

### Decision

**Framework**: Position Trading + Multi-Factor Analysis + Multi-Asset Portfolio

**Specific Implementation**:
- **Strategy Type**: Multi-Factor Portfolio Strategy
- **Trading Frequency**: Position trading with weekly/monthly rebalancing
- **Holding Method**: Multi-asset portfolio (5-20 simultaneous positions)
- **Timeframe**: Daily bars (end-of-day data)

### Rationale

**1. Low Time Investment**
- Daily bar data, run once per day after market close
- No intraday monitoring required
- Weekly or monthly rebalancing minimizes trading frequency
- ✅ Perfect for part-time operation

**2. Capital Efficiency**
- Diversification reduces single-stock risk
- No massive capital requirement like HFT
- Starting capital: $10,000+ ($500-2,000 per position)

**3. Appropriate Technical Complexity**
- No microsecond infrastructure needed (vs HFT)
- No real-time news parsing needed (vs news-driven strategies)
- Mature libraries available (TA-Lib + pandas)

**4. Strong Explainability**
- Based on classic technical indicators and factors
- Easy to debug and understand
- Aligns with "use mature libraries" principle

**5. Excellent Scalability**
- Phase 1: Simple dual moving average, single factor
- Phase 2: Add RSI, MACD, multi-factor combination
- Phase 3: Incorporate fundamental factors, machine learning

**6. Controllable Risk**
- Natural diversification across positions
- Single-position limits enforceable (e.g., 10% max)
- Easy to implement stop-loss and position sizing

## Progressive Implementation Roadmap

### Phase 1: Single-Factor Trend-Following Portfolio (Initial)

**Objective**: Validate end-to-end system workflow

```
Universe: 20-30 liquid large-cap stocks
Factor: Moving average crossover (single signal source)
Portfolio Construction: Equal-weight 5-10 stocks with buy signals
Rebalancing: Weekly
Expected Sharpe: 0.5-1.0 (baseline)
```

**Key Goals**:
- Prove the complete system pipeline works
- Establish data → signal → portfolio → execution flow
- Collect real performance data for iteration

### Phase 2: Multi-Factor Portfolio (Mid-term)

**Objective**: Improve risk-adjusted returns

```
Universe: Expand to 50-100 stocks
Factors:
  - Trend: MA, MACD
  - Momentum: RSI, ROC (Rate of Change)
  - Volatility: ATR, Bollinger Bands
Portfolio Construction: Factor-weighted or optimization algorithm
Rebalancing: Bi-weekly
Expected Sharpe: 1.0-1.5 (target)
```

**Key Goals**:
- Improve Sharpe ratio through factor diversification
- Test different factor weighting schemes
- Validate robustness across market conditions

### Phase 3: Fundamental-Enhanced Portfolio (Advanced)

**Objective**: More robust long-term performance

```
Additional Factors:
  - Valuation: P/E, P/B, PEG ratio
  - Quality: ROE, Profit Margin, Debt/Equity
  - Growth: Revenue growth, Earnings growth
Portfolio Optimization: Markowitz Mean-Variance or Black-Litterman
Rebalancing: Monthly
Expected Sharpe: 1.5+ (aspirational)
```

**Key Goals**:
- Combine technical and fundamental signals
- Sophisticated portfolio optimization
- Production-ready systematic trading system

## Strategy Architecture

### Layer Hierarchy

```
┌─────────────────────────────────────┐
│   Portfolio Management Layer        │
│   (Aggregates signals, allocates    │
│    capital, generates rebalancing   │
│    instructions)                    │
└──────────────┬──────────────────────┘
               ↓
       ┌───────────────┐
       │ Strategy Base │ (Abstract Interface)
       └───────┬───────┘
               ↓
    ┌──────────┴──────────┐
    ↓                     ↓
┌──────────┐         ┌──────────┐
│ MA Cross │         │   RSI    │
│ Strategy │         │ Strategy │
└─────┬────┘         └────┬─────┘
      │                   │
      └────────┬──────────┘
               ↓
┌─────────────────────────────┐
│   Indicator Library         │
│   (TA-Lib: MA, RSI, MACD,   │
│    ATR, Bollinger, etc.)    │
└─────────────────────────────┘
```

### Strategy Base Class Design

The abstract `Strategy` class defines the contract for all strategy implementations:

```python
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict

class Strategy(ABC):
    """
    Abstract base class for all trading strategies.

    Each strategy analyzes market data and outputs directional signals
    with confidence scores, without knowledge of portfolio allocation.
    """

    def __init__(self, params: Dict):
        """
        Initialize strategy with parameters.

        Args:
            params: Strategy-specific parameters (e.g., {'fast_period': 20, 'slow_period': 50})
        """
        self.params = params
        self.validate_params()

    @abstractmethod
    def validate_params(self) -> None:
        """Validate that required parameters are present and valid."""
        pass

    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators needed for signal generation.

        Separated from signal generation for debugging and inspection.

        Args:
            data: OHLCV DataFrame from DataProvider
                  Columns: [timestamp, open, high, low, close, volume]

        Returns:
            DataFrame with additional indicator columns
        """
        pass

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on market data.

        This is the core strategy logic.

        Args:
            data: OHLCV DataFrame (from DataProvider)

        Returns:
            Series: Signal values in range [-1.0, 1.0]
                   Index: timestamps
                   Values: Direction + Confidence (see Signal Semantics below)
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate data quality before processing.

        Checks:
        - Sufficient data points
        - No excessive missing values
        - Reasonable price ranges (no obvious errors)

        Returns:
            True if data passes validation
        """
        # Default implementation
        required_rows = self.params.get('min_required_rows', 100)
        if len(data) < required_rows:
            return False

        # Check for NaN in critical columns
        if data[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum() > 0:
            return False

        return True
```

### Signal Semantics: Direction + Confidence

**Critical Design Decision**: Strategy signals represent **directional conviction**, not position sizes or expected returns.

#### Signal Definition

```python
class Signal:
    """
    Trading signal representation.

    value: float in range [-1.0, 1.0]
        - Sign indicates direction:
            > 0: Bullish (buy signal)
            < 0: Bearish (sell signal)
            = 0: Neutral (hold/no opinion)

        - Magnitude indicates confidence:
            0.0 - 0.3: Weak signal
            0.3 - 0.7: Medium signal
            0.7 - 1.0: Strong signal

    Examples:
         0.9  : Strong bullish conviction → high-confidence buy
         0.5  : Medium bullish conviction → moderate buy
         0.1  : Weak bullish conviction → marginal buy
         0.0  : Completely neutral
        -0.5  : Medium bearish conviction → moderate sell
        -0.9  : Strong bearish conviction → high-confidence sell
    """
```

#### Why Direction + Confidence (vs Alternatives)?

We considered three approaches:

**Option 1: Direction + Confidence** ✅ **SELECTED**
- Meaning: Confidence in directional movement
- Range: [-1.0, 1.0] where magnitude = conviction strength
- Pros: Intuitive, flexible, easy to combine multiple factors
- Cons: Requires mapping to position sizes in Portfolio Layer

**Option 2: Expected Return**
- Meaning: Predicted future return percentage
- Range: e.g., 0.15 = expecting +15% return
- Pros: Direct economic meaning, works with optimization algorithms
- Cons: Hard to estimate accurately from technical indicators

**Option 3: Normalized Rank Score**
- Meaning: Relative ranking among universe
- Range: 0.0 (worst) to 1.0 (best) based on percentile
- Pros: Natural for "buy top N" strategies, removes scaling issues
- Cons: Loses absolute strength information, purely relative

**Decision Rationale**:
- Technical indicators naturally express "strength" not "expected return"
- Flexible enough to evolve: Phase 1 (confidence) → Phase 3 (calibrated to returns)
- Clean separation: Strategy = "what to buy", Portfolio = "how much to buy"
- Easy multi-factor combination through weighted averaging

#### Multi-Factor Signal Combination Example

```python
# Individual factor signals
ma_signal = 0.6      # MA crossover: moderate bullish
rsi_signal = 0.4     # RSI: slightly oversold
macd_signal = 0.8    # MACD: strong momentum

# Weighted combination (weights sum to 1.0)
final_signal = 0.4 * ma_signal + 0.3 * rsi_signal + 0.3 * macd_signal
# = 0.4*0.6 + 0.3*0.4 + 0.3*0.8 = 0.6 (medium-strong buy)
```

#### Signal-to-Position Translation (Portfolio Layer's Job)

The Portfolio Management Layer translates signals into position weights:

```python
def signals_to_weights(signals: Dict[str, float]) -> Dict[str, float]:
    """
    Example: Simple threshold-based allocation

    Args:
        signals: {'AAPL': 0.8, 'MSFT': 0.5, 'GOOGL': 0.2, 'TSLA': -0.6}

    Returns:
        weights: {'AAPL': 0.554, 'MSFT': 0.346, 'Cash': 0.1}
    """
    # Filter: only signals > 0.3 (ignore weak signals)
    strong_signals = {k: v for k, v in signals.items() if v > 0.3}

    if not strong_signals:
        return {'Cash': 1.0}

    # Allocate 90% of capital (10% cash buffer)
    total_strength = sum(strong_signals.values())
    weights = {
        symbol: (signal / total_strength) * 0.9
        for symbol, signal in strong_signals.items()
    }
    weights['Cash'] = 0.1

    return weights
```

**Evolution Path**:
- Phase 1: Simple thresholding (as above)
- Phase 2: Calibrate signals to historical returns
- Phase 3: Use signals as inputs to Markowitz/Black-Litterman optimization

## Technical Indicator Library

### Decision: TA-Lib (Primary)

**Rationale**:
- ✅ Industry-standard algorithms (30+ years of validation)
- ✅ C implementation for performance (important for backtesting large universes)
- ✅ 150+ indicators covering all common needs
- ✅ **Easy installation in Ubuntu DevContainer** (apt-get + pip)
- ⚠️ API is not as Pythonic as pandas-ta (requires numpy array extraction)

**Installation** (in DevContainer):
```bash
# System library
sudo apt-get install -y libta-lib0-dev

# Python wrapper
pip install TA-Lib
```

**Usage Example**:
```python
import talib
import pandas as pd

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    close = data['close'].values
    high = data['high'].values
    low = data['low'].values

    # Calculate indicators
    data['sma_20'] = talib.SMA(close, timeperiod=20)
    data['sma_50'] = talib.SMA(close, timeperiod=50)
    data['rsi'] = talib.RSI(close, timeperiod=14)

    macd, macd_signal, macd_hist = talib.MACD(close,
                                               fastperiod=12,
                                               slowperiod=26,
                                               signalperiod=9)
    data['macd'] = macd
    data['macd_signal'] = macd_signal
    data['macd_hist'] = macd_hist

    return data
```

### Optional: pandas-ta (Supplementary)

**When to Use**:
- Indicators not available in TA-Lib
- Rapid prototyping (more Pythonic API)
- Educational exploration

**Installation**:
```bash
pip install pandas-ta
```

**Mixed Usage Strategy**:
- Primary: TA-Lib for core indicators (MA, RSI, MACD, Bollinger, ATR)
- Supplementary: pandas-ta for specialized/newer indicators
- Abstraction: Hide library choice behind `calculate_indicators()` method

## Concrete Strategy Example: MA Crossover

A simple moving average crossover strategy to illustrate the design:

```python
class MACrossStrategy(Strategy):
    """
    Moving Average Crossover Strategy

    Signal Logic:
    - Golden Cross (fast MA crosses above slow MA): BUY signal (1.0)
    - Death Cross (fast MA crosses below slow MA): SELL signal (-1.0)
    - Otherwise: HOLD (0.0)

    Parameters:
    - fast_period: Fast MA period (default: 20)
    - slow_period: Slow MA period (default: 50)
    """

    def validate_params(self) -> None:
        required = ['fast_period', 'slow_period']
        for param in required:
            if param not in self.params:
                raise ValueError(f"Missing required parameter: {param}")

        if self.params['fast_period'] >= self.params['slow_period']:
            raise ValueError("fast_period must be < slow_period")

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        import talib

        close = data['close'].values

        data['sma_fast'] = talib.SMA(close, timeperiod=self.params['fast_period'])
        data['sma_slow'] = talib.SMA(close, timeperiod=self.params['slow_period'])

        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        # Ensure indicators are calculated
        if 'sma_fast' not in data.columns:
            data = self.calculate_indicators(data)

        # Initialize neutral signals
        signals = pd.Series(0.0, index=data.index)

        # Detect crossovers
        # Golden cross: fast crosses above slow
        golden_cross = (
            (data['sma_fast'] > data['sma_slow']) &
            (data['sma_fast'].shift(1) <= data['sma_slow'].shift(1))
        )

        # Death cross: fast crosses below slow
        death_cross = (
            (data['sma_fast'] < data['sma_slow']) &
            (data['sma_fast'].shift(1) >= data['sma_slow'].shift(1))
        )

        # Assign signals
        signals[golden_cross] = 1.0   # Strong buy
        signals[death_cross] = -1.0   # Strong sell

        return signals
```

**Usage**:
```python
# Initialize strategy
strategy = MACrossStrategy(params={'fast_period': 20, 'slow_period': 50})

# Get data from Data Layer
data = data_provider.get_historical_bars('AAPL', start_date, end_date, '1d')

# Generate signals
signals = strategy.generate_signals(data)

# Output:
# 2024-01-15    0.0
# 2024-01-16    1.0   ← Golden cross
# 2024-01-17    0.0
# ...
# 2024-06-20   -1.0   ← Death cross
```

## Strategy Composition Patterns

### Pattern 1: Weighted Voting (Additive)

Multiple strategies vote, weighted average determines final signal:

```python
class CompositeStrategy(Strategy):
    def __init__(self, strategies: List[Tuple[Strategy, float]]):
        """
        Args:
            strategies: List of (strategy, weight) tuples
                        Weights should sum to 1.0
        """
        self.strategies = strategies

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        combined = pd.Series(0.0, index=data.index)

        for strategy, weight in self.strategies:
            signal = strategy.generate_signals(data)
            combined += weight * signal

        # Clip to [-1, 1] range
        return combined.clip(-1.0, 1.0)

# Example usage
composite = CompositeStrategy([
    (MACrossStrategy({'fast_period': 20, 'slow_period': 50}), 0.4),
    (RSIStrategy({'period': 14, 'oversold': 30, 'overbought': 70}), 0.3),
    (MACDStrategy({'fast': 12, 'slow': 26, 'signal': 9}), 0.3)
])
```

### Pattern 2: Conditional Filtering (Gating)

Only generate signal when multiple strategies agree:

```python
class ConsensusStrategy(Strategy):
    def __init__(self, strategies: List[Strategy], min_agreement: float = 0.5):
        """
        Args:
            strategies: List of strategies
            min_agreement: Minimum fraction of strategies that must agree
        """
        self.strategies = strategies
        self.min_agreement = min_agreement

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        signals = [s.generate_signals(data) for s in self.strategies]

        # Count bullish/bearish consensus
        bullish_votes = sum((s > 0).astype(int) for s in signals)
        bearish_votes = sum((s < 0).astype(int) for s in signals)

        total = len(self.strategies)
        threshold = total * self.min_agreement

        result = pd.Series(0.0, index=data.index)
        result[bullish_votes >= threshold] = 1.0
        result[bearish_votes >= threshold] = -1.0

        return result
```

## Integration with Backtesting

### Design Choice: Adapter Pattern

**Option 1**: Tightly couple with Backtrader ❌
- Pros: Deep integration, rich features
- Cons: Hard to migrate, can't use strategies outside Backtrader

**Option 2**: Independent strategy framework with adapters ✅ **SELECTED**
- Pros: Strategies work in backtesting AND live trading, framework-agnostic
- Cons: Need to write adapter layer

**Implementation**:
```python
# Our strategy (framework-agnostic)
ma_strategy = MACrossStrategy({'fast_period': 20, 'slow_period': 50})

# Adapter for Backtrader
class BacktraderStrategyAdapter(bt.Strategy):
    def __init__(self):
        self.our_strategy = ma_strategy

    def next(self):
        # Convert Backtrader data to our DataFrame format
        data = self.convert_to_dataframe(self.data)

        # Generate signal using our strategy
        signal = self.our_strategy.generate_signals(data).iloc[-1]

        # Execute based on signal
        if signal > 0.5 and not self.position:
            self.buy()
        elif signal < -0.5 and self.position:
            self.sell()
```

**Benefits**:
- Same strategy code for backtesting and live trading
- Can switch backtesting frameworks without rewriting strategies
- Cleaner separation of concerns

## Parameter Optimization (Future Consideration)

**Not in initial scope**, but design accommodates:

```python
# Grid search example (conceptual)
param_grid = {
    'fast_period': [10, 20, 30],
    'slow_period': [50, 100, 200]
}

best_params = None
best_sharpe = -999

for fast in param_grid['fast_period']:
    for slow in param_grid['slow_period']:
        strategy = MACrossStrategy({'fast_period': fast, 'slow_period': slow})
        sharpe = backtest(strategy, data)

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = {'fast_period': fast, 'slow_period': slow}
```

Advanced optimization (genetic algorithms, Bayesian optimization) can be added in Phase 2-3.

## Key Design Principles Summary

1. ✅ **Single Responsibility**: Strategies only generate signals, not allocations
2. ✅ **Abstraction**: Clean interface separates strategy logic from infrastructure
3. ✅ **Composability**: Strategies can be combined via weighted voting or consensus
4. ✅ **Testability**: Pure functions, easy to unit test with sample data
5. ✅ **Extensibility**: Easy to add new strategies without modifying existing code
6. ✅ **Framework Independence**: Not locked into any backtesting framework

## Related Documents

- [tech-stack.md](tech-stack.md) - TA-Lib selection rationale
- [data-layer-design.md](data-layer-design.md) - Data format consumed by strategies
- [architecture-overview.md](architecture-overview.md) - How strategy layer fits in system (TBD)
- Portfolio Management Layer design document (TBD - next discussion topic)

## Next Steps

1. ✅ Strategy Layer design complete
2. ⏳ Discuss Portfolio Management Layer (capital allocation logic)
3. ⏳ Discuss Risk Management Layer (safety constraints)
4. ⏳ Discuss Execution Layer (order routing)
5. ⏳ Finalize overall architecture diagram
