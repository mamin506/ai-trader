# Portfolio Management Layer Design

**Status**: ✅ Decided (2026-01-17)

## Overview

The Portfolio Management Layer sits between the Strategy Layer and Risk Management Layer. It is responsible for translating trading signals from multiple securities into concrete portfolio allocations and rebalancing instructions.

**Key Insight**: Unlike other layers, this is **not primarily about choosing third-party libraries**, but rather about selecting and implementing **allocation algorithms and portfolio theory**.

## Core Responsibilities

1. **Signal Aggregation**: Collect signals from Strategy Layer for all securities in the universe
2. **Weight Allocation**: Determine target portfolio weights (% of capital per security)
3. **Cash Management**: Decide how much cash to hold as buffer
4. **Rebalancing Logic**: Calculate the difference between current and target positions
5. **Order Generation**: Translate position changes into executable orders for Execution Layer

**What This Layer Does NOT Do**:
- ❌ Generate trading signals (Strategy Layer's job)
- ❌ Enforce risk limits or stop-loss (Risk Management Layer's job)
- ❌ Execute orders (Execution Layer's job)

## Input and Output

### Input
```python
# From Strategy Layer
signals: Dict[str, float] = {
    'AAPL': 0.8,   # Strong buy
    'MSFT': 0.5,   # Medium buy
    'GOOGL': 0.3,  # Weak buy
    'TSLA': -0.6,  # Medium sell
    'AMZN': 0.0,   # Neutral
}

# Current portfolio state
current_portfolio = {
    'positions': {'MSFT': 10000, 'TSLA': 5000, 'Cash': 85000},
    'total_value': 100000,
    'prices': {'AAPL': 150, 'MSFT': 350, 'GOOGL': 140, 'TSLA': 250}
}
```

### Output
```python
# Target portfolio weights
target_weights: Dict[str, float] = {
    'AAPL': 0.25,   # 25% of portfolio
    'MSFT': 0.15,   # 15% of portfolio
    'GOOGL': 0.05,  # 5% of portfolio
    'Cash': 0.55    # 55% cash (includes buffer + filtered signals)
}

# Rebalancing orders
orders: List[Order] = [
    Order('BUY', 'AAPL', 166 shares),   # $25,000 / $150
    Order('BUY', 'MSFT', 14 shares),    # Increase from $10k to $15k
    Order('BUY', 'GOOGL', 35 shares),   # $5,000 / $140
    Order('SELL', 'TSLA', 20 shares),   # Exit position
]
```

## Why No Standard Library?

Unlike Data Layer (yfinance) or Strategy Layer (TA-Lib), there is **no comprehensive off-the-shelf solution** for portfolio management. Here's why:

1. **Highly Customized Logic**: Every trader has different rules (cash buffer, rebalancing frequency, position limits)
2. **Algorithmic Choice**: Multiple valid approaches (equal weight, risk parity, optimization)
3. **Integration Complexity**: Needs to integrate signals, risk constraints, and execution logic

### Available Tools (Not Complete Solutions)

**PyPortfolioOpt** ⭐ Recommended for optimization algorithms
- **What it provides**: Implementations of Markowitz, Black-Litterman, Risk Parity, HRP
- **What it doesn't provide**: Signal filtering, rebalancing logic, cash management, order generation
- **Use case**: Optimization engine within our custom Portfolio Manager

**Riskfolio-Lib**
- More academic, supports advanced risk measures (CVaR, drawdown optimization)
- Steeper learning curve
- May use in Phase 3 for advanced scenarios

**QuantLib-Python**
- Professional financial engineering library
- Overkill for equity portfolio management
- Better suited for derivatives pricing

**Conclusion**: We implement the Portfolio Management Layer ourselves, potentially using PyPortfolioOpt as an optimization component in Phase 2-3.

## Portfolio Theory and Algorithms

### Theory 1: Modern Portfolio Theory (MPT) - Markowitz Optimization

**Core Idea**: Maximize expected return for a given level of risk, or minimize risk for a given expected return.

**Mathematical Formulation**:
```
Objective: Minimize portfolio variance
    min w^T Σ w

Constraints:
    - w^T μ ≥ target_return  (minimum expected return)
    - w^T 1 = 1              (weights sum to 1)
    - w ≥ 0                  (no short selling)
    - w_i ≤ max_weight       (position limits)

Where:
    w = weight vector
    Σ = covariance matrix
    μ = expected returns vector
```

**Advantages**:
- Mathematically rigorous, globally optimal solution
- Considers correlations between assets (diversification benefit)
- Well-established theory with decades of validation

**Disadvantages**:
- **Extremely sensitive** to expected return estimates (small errors → large portfolio changes)
- Requires covariance matrix (needs sufficient historical data)
- May produce extreme/concentrated portfolios without constraints
- "Garbage in, garbage out" - poor return estimates = poor portfolios

**Implementation with PyPortfolioOpt**:
```python
from pypfopt import EfficientFrontier, risk_models, expected_returns

# Calculate inputs
mu = expected_returns.mean_historical_return(historical_prices)
S = risk_models.sample_cov(historical_prices)

# Optimize
ef = EfficientFrontier(mu, S)
ef.add_constraint(lambda w: w <= 0.20)  # Max 20% per position
weights = ef.max_sharpe()  # Maximize Sharpe ratio

# Clean up small weights
weights = ef.clean_weights()
```

**When to Use**: Phase 3, when we have reliable return estimates and want sophisticated optimization.

### Theory 2: Risk Parity

**Core Idea**: Each asset contributes equally to total portfolio risk (not capital).

```
Traditional equal weighting: Each asset gets 1/N of capital
Risk Parity: Each asset contributes 1/N of risk

Result:
- High volatility assets → Lower weight
- Low volatility assets → Higher weight
```

**Advantages**:
- **Does not require expected return estimates** (only volatility/covariance)
- More robust than Markowitz (fewer inputs = less estimation error)
- Tends to produce more balanced portfolios
- Works well in "risk-on/risk-off" market environments

**Disadvantages**:
- Ignores expected returns (may allocate to low-return assets)
- Can be too conservative (overweight low-vol = potentially lower returns)
- Not directly using our strategy signals

**Implementation**:
```python
from pypfopt import HRPOpt  # Hierarchical Risk Parity

hrp = HRPOpt(returns_data)
weights = hrp.optimize()
```

**When to Use**: Phase 2, as a robust baseline or complement to signal-based allocation.

### Theory 3: Black-Litterman Model

**Core Idea**: Combine market equilibrium (implied returns) with investor views (our signals) using Bayesian inference.

```
Market Equilibrium: Current market prices imply "consensus" expected returns
Investor Views: Our strategy signals provide "subjective" adjustments
Bayesian Fusion: Blend both to get adjusted expected returns

Advantage: More stable than pure historical estimates
```

**Process**:
1. Start with market-implied returns (from current prices)
2. Express our signals as "views" (e.g., "AAPL will outperform by 5%")
3. Specify confidence in each view (signal strength → confidence)
4. Bayesian update to get posterior expected returns
5. Feed to Markowitz optimizer

**Advantages**:
- More stable than raw historical returns
- Naturally integrates our strategy signals as "views"
- Academically sound framework

**Disadvantages**:
- Conceptually complex (requires understanding Bayesian inference)
- Many parameters to tune (view confidence, tau, etc.)
- Potentially overkill for Phase 1

**When to Use**: Phase 3, when combining multiple factor signals and seeking sophisticated integration.

### Method 4: Heuristic Rule-Based Allocation ⭐ Phase 1 Choice

**Core Idea**: Simple, transparent rules for allocation without optimization.

**Equal Weight**:
```python
# All qualified securities get equal allocation
buy_signals = [s for s in signals if s > threshold]
weight_per_asset = investable_capital / len(buy_signals)
```

**Signal Strength Weighting**:
```python
# Allocate proportional to signal strength
total_strength = sum(max(0, s) for s in signals.values())
weights = {
    symbol: (signal / total_strength) * investable_ratio
    for symbol, signal in signals.items()
    if signal > threshold
}
```

**Advantages**:
- ✅ Extremely simple to implement and understand
- ✅ Fast computation (no matrix operations)
- ✅ Transparent logic (easy to debug and explain)
- ✅ No historical data requirements (works from day 1)
- ✅ Directly uses our signals

**Disadvantages**:
- ❌ Ignores diversification benefits (correlations)
- ❌ Ignores risk differences (treats high-vol and low-vol equally)
- ❌ May produce concentrated portfolios if all signals point same direction

**Why Start Here**: Perfect for Phase 1 to validate the entire system pipeline. Establishes baseline performance for future optimization.

## Progressive Implementation Plan

### Phase 1: Simple Rule-Based Allocation (IMMEDIATE)

**Objective**: Get the system working end-to-end with transparent, debuggable logic.

**Algorithm**: Signal Strength Weighting + Basic Rules

**Implementation**:
```python
class SimplePortfolioManager:
    """
    Phase 1: Heuristic rule-based portfolio allocation.

    Rules:
    - Only invest in signals above threshold (filter weak signals)
    - Select top N strongest signals (limit positions)
    - Allocate proportional to signal strength
    - Enforce single-position size limit
    - Maintain cash buffer
    """

    def __init__(self, config: Dict):
        self.min_signal_threshold = config.get('min_signal', 0.3)
        self.max_positions = config.get('max_positions', 10)
        self.cash_buffer = config.get('cash_buffer', 0.10)  # 10%
        self.max_position_size = config.get('max_position', 0.20)  # 20%

    def calculate_target_weights(self,
                                 signals: Dict[str, float]) -> Dict[str, float]:
        """
        Convert signals to target portfolio weights.

        Args:
            signals: {symbol: signal_value} from Strategy Layer

        Returns:
            {symbol: weight} where weights sum to 1.0
        """
        # Step 1: Filter weak signals (only strong convictions)
        strong_signals = {
            symbol: signal
            for symbol, signal in signals.items()
            if signal > self.min_signal_threshold
        }

        # Step 2: Select top N strongest signals (limit positions)
        top_signals = dict(sorted(
            strong_signals.items(),
            key=lambda x: x[1],
            reverse=True
        )[:self.max_positions])

        if not top_signals:
            # No strong signals → 100% cash
            return {'Cash': 1.0}

        # Step 3: Allocate proportional to signal strength
        total_strength = sum(top_signals.values())
        investable_ratio = 1.0 - self.cash_buffer

        weights = {}
        for symbol, signal in top_signals.items():
            weight = (signal / total_strength) * investable_ratio

            # Step 4: Cap individual position size (risk control)
            weight = min(weight, self.max_position_size)
            weights[symbol] = weight

        # Step 5: Renormalize and calculate cash
        total_allocated = sum(weights.values())
        if total_allocated > 0:
            # Scale down if we hit position limits
            scale_factor = investable_ratio / total_allocated
            weights = {k: v * scale_factor for k, v in weights.items()}

        weights['Cash'] = 1.0 - sum(weights.values())

        return weights


class Rebalancer:
    """
    Translates target weights into executable orders.
    """

    def __init__(self, config: Dict):
        self.min_trade_value = config.get('min_trade_value', 100)

    def generate_orders(self,
                       current_positions: Dict[str, float],
                       target_weights: Dict[str, float],
                       total_portfolio_value: float,
                       current_prices: Dict[str, float]) -> List:
        """
        Calculate orders needed to move from current to target portfolio.

        Args:
            current_positions: {symbol: dollar_value} current holdings
            target_weights: {symbol: weight} target allocation
            total_portfolio_value: Total account value
            current_prices: {symbol: price} latest prices

        Returns:
            List of Order objects
        """
        # Calculate target dollar positions
        target_positions = {
            symbol: weight * total_portfolio_value
            for symbol, weight in target_weights.items()
            if symbol != 'Cash'
        }

        orders = []

        # Check all symbols (current holdings + target positions)
        all_symbols = set(list(current_positions.keys()) +
                         list(target_positions.keys()))
        all_symbols.discard('Cash')

        for symbol in all_symbols:
            current_value = current_positions.get(symbol, 0.0)
            target_value = target_positions.get(symbol, 0.0)

            diff_value = target_value - current_value

            # Ignore small trades (avoid excessive transaction costs)
            if abs(diff_value) < self.min_trade_value:
                continue

            price = current_prices.get(symbol)
            if price is None:
                continue  # Skip if no price available

            # Convert dollar difference to shares
            shares = int(diff_value / price)

            if shares > 0:
                orders.append({
                    'action': 'BUY',
                    'symbol': symbol,
                    'shares': shares,
                    'estimated_value': shares * price
                })
            elif shares < 0:
                orders.append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'shares': abs(shares),
                    'estimated_value': abs(shares) * price
                })

        return orders


class PortfolioManager:
    """
    Main Portfolio Management orchestrator (Phase 1).
    """

    def __init__(self, config: Dict):
        self.allocator = SimplePortfolioManager(config)
        self.rebalancer = Rebalancer(config)

    def process_signals(self,
                       signals: Dict[str, float],
                       current_portfolio: Dict,
                       current_prices: Dict[str, float]) -> Dict:
        """
        Main entry point: signals → target weights → orders.

        Returns:
            {
                'target_weights': {...},
                'orders': [...]
            }
        """
        # Step 1: Calculate target allocation
        target_weights = self.allocator.calculate_target_weights(signals)

        # Step 2: Generate rebalancing orders
        orders = self.rebalancer.generate_orders(
            current_positions=current_portfolio['positions'],
            target_weights=target_weights,
            total_portfolio_value=current_portfolio['total_value'],
            current_prices=current_prices
        )

        return {
            'target_weights': target_weights,
            'orders': orders
        }
```

**Configuration Example**:
```yaml
portfolio_management:
  min_signal: 0.3          # Only trade signals > 0.3
  max_positions: 10        # Hold at most 10 stocks
  cash_buffer: 0.10        # Keep 10% cash
  max_position_size: 0.20  # Single stock max 20%
  min_trade_value: 100     # Ignore trades < $100
```

**Why This Works for Phase 1**:
- Simple enough to implement in a day
- Transparent logic for debugging
- Good enough to validate the system
- Establishes performance baseline

### Phase 2: Risk-Adjusted Allocation (MID-TERM)

**Objective**: Improve risk-adjusted returns by considering volatility.

**Enhancement**: Adjust signal strength by volatility (risk-adjusted scoring).

```python
class RiskAdjustedPortfolioManager(SimplePortfolioManager):
    """
    Phase 2: Incorporate volatility into allocation decisions.
    """

    def calculate_target_weights(self,
                                 signals: Dict[str, float],
                                 historical_prices: pd.DataFrame) -> Dict[str, float]:
        """
        Adjust signals by inverse volatility before allocation.

        Logic: High signal + Low volatility = Best candidates
        """
        # Calculate historical volatility
        returns = historical_prices.pct_change().dropna()
        volatilities = returns.std()

        # Risk-adjusted signals: signal / volatility
        # (High signal, low vol → high score)
        risk_adjusted_signals = {}
        for symbol, signal in signals.items():
            if signal > self.min_signal_threshold and symbol in volatilities:
                # Inverse volatility weighting
                risk_adjusted_signals[symbol] = signal / volatilities[symbol]

        # Continue with standard allocation using adjusted signals
        return super()._allocate_by_strength(risk_adjusted_signals)
```

**Alternative: Minimum Variance Overlay**
```python
# Use simple allocation, then apply minimum variance optimization
base_weights = self.simple_allocator.calculate_target_weights(signals)
candidates = [s for s in base_weights if s != 'Cash']

# Optimize only within candidate set
prices_subset = historical_prices[candidates]
S = risk_models.sample_cov(prices_subset)

# Minimize variance while staying close to base weights
# (Constrained optimization)
```

**When to Implement**: After Phase 1 baseline is established and we have performance data.

### Phase 3: Portfolio Optimization (ADVANCED)

**Objective**: Sophisticated allocation using modern portfolio theory.

**Approach**: Integrate signals into Black-Litterman → Markowitz optimization.

```python
class OptimizedPortfolioManager:
    """
    Phase 3: Full portfolio optimization with signal integration.
    """

    def __init__(self, config: Dict):
        self.config = config

    def calculate_target_weights(self,
                                 signals: Dict[str, float],
                                 historical_prices: pd.DataFrame) -> Dict[str, float]:
        """
        Use signals as Black-Litterman views, optimize with Markowitz.
        """
        from pypfopt import BlackLittermanModel, EfficientFrontier
        from pypfopt import risk_models, expected_returns

        # Filter to candidate assets
        candidates = [s for s, v in signals.items() if v > self.config['min_signal']]
        prices_subset = historical_prices[candidates]

        # Market-implied equilibrium returns
        S = risk_models.sample_cov(prices_subset)
        delta = 2.5  # Risk aversion parameter
        market_prior = expected_returns.capm_return(prices_subset)

        # Convert our signals to "views" (expected outperformance)
        viewdict = {}
        confidence = []
        for symbol in candidates:
            # Strong signal → expect higher return
            # Convert signal [0, 1] to expected excess return
            viewdict[symbol] = signals[symbol] * 0.10  # Max 10% expected excess
            confidence.append(signals[symbol])  # Signal strength = confidence

        # Black-Litterman fusion
        bl = BlackLittermanModel(S, pi=market_prior,
                                 absolute_views=viewdict,
                                 omega="idzorek",  # Confidence-weighted
                                 view_confidences=confidence)

        posterior_returns = bl.bl_returns()

        # Markowitz optimization with posterior returns
        ef = EfficientFrontier(posterior_returns, S)
        ef.add_constraint(lambda w: w <= self.config['max_position_size'])
        ef.add_constraint(lambda w: w >= 0)  # Long-only

        weights = ef.max_sharpe()
        weights = ef.clean_weights(cutoff=0.01)  # Remove tiny positions

        # Add cash buffer
        investable = 1.0 - self.config['cash_buffer']
        weights = {k: v * investable for k, v in weights.items()}
        weights['Cash'] = self.config['cash_buffer']

        return weights
```

**When to Implement**: Phase 3, after validating that Phase 1-2 work and we want to squeeze out more performance.

**Dependencies**:
```bash
pip install PyPortfolioOpt
```

## Key Design Decisions

### Decision 1: Rebalancing Frequency

**Trade-off**: Responsiveness vs Transaction Costs

| Frequency | Pros | Cons | Best For |
|-----------|------|------|----------|
| Daily | Track signals closely | High transaction costs, overtrading | High-turnover strategies |
| Weekly | Balanced | Moderate costs | **Phase 1 choice** |
| Monthly | Low costs | May miss rapid changes | Low-turnover, long-term |
| Threshold-based | Efficient | Complex logic | Phase 2+ |

**Phase 1 Decision**: **Weekly rebalancing** (fixed schedule, e.g., every Monday after market close)

**Phase 2 Enhancement**: Add threshold logic - only rebalance if portfolio drift > 5%

```python
def should_rebalance(current_weights, target_weights, threshold=0.05):
    """Only rebalance if any position drifted > threshold."""
    for symbol in target_weights:
        drift = abs(current_weights.get(symbol, 0) - target_weights[symbol])
        if drift > threshold:
            return True
    return False
```

### Decision 2: Sell Rules

**When to exit a position?**

**Option A: Signal Reversal** (Aggressive)
```python
if signal < 0:  # Now a sell signal
    exit_position()
```

**Option B: Signal Weakening** (Conservative) ✅ **Phase 1 Choice**
```python
if signal < min_signal_threshold:  # Below 0.3
    exit_position()
```

**Option C: Rolling Optimization** (Sophisticated)
```python
# Every rebalance, recalculate optimal portfolio
# Naturally reduces/exits positions as signals weaken
```

**Phase 1 Decision**: Option B - Exit when signal drops below threshold (0.3)
- Clear rule, easy to understand
- Avoids whipsaw from signal noise
- Natural hysteresis (buy at 0.3, sell when drops below 0.3)

### Decision 3: Cash Buffer

**How much cash to maintain?**

**Static Approach** (Phase 1) ✅:
```python
cash_buffer = 0.10  # Always keep 10%
```

**Dynamic Approach** (Phase 2+):
```python
# Adjust based on market conditions
if market_volatility > threshold:
    cash_buffer = 0.20  # Defensive: hold more cash
else:
    cash_buffer = 0.05  # Aggressive: fully invested
```

**Phase 1 Decision**: Static 10% cash buffer
- Simple, predictable
- Handles unexpected opportunities or margin calls
- Room to add positions without forced selling

### Decision 4: Position Limits

**Single-position maximum weight**: 20% (configurable)

**Rationale**:
- Prevents over-concentration risk
- With 10 max positions, could theoretically be 90% invested across 5+ stocks
- Conservative enough for Phase 1

**Alternative constraints for Phase 2+**:
- Sector limits (max 30% in tech)
- Correlation-based limits (correlated stocks collectively limited)

## Integration with Other Layers

### From Strategy Layer

**Input**: Signals with direction + confidence
```python
{
    'AAPL': 0.8,   # 80% confidence bullish
    'MSFT': 0.5,   # 50% confidence bullish
    'GOOGL': 0.2,  # Weak signal (likely filtered)
    'TSLA': -0.6   # 60% confidence bearish
}
```

**Expectation**: Strategy Layer provides signals for **all** securities in the universe, not just "buy" candidates.

### To Risk Management Layer

**Output**: Target weights for validation
```python
target_weights = {
    'AAPL': 0.25,
    'MSFT': 0.15,
    'Cash': 0.60
}

# Risk layer checks:
# - Single position not > max_position_size
# - Sector concentration acceptable
# - Leverage within limits
# - etc.
```

**Feedback Loop**: Risk layer may reject or adjust weights, Portfolio layer regenerates orders.

### To Execution Layer

**Output**: List of orders
```python
orders = [
    {'action': 'BUY', 'symbol': 'AAPL', 'shares': 100},
    {'action': 'SELL', 'symbol': 'TSLA', 'shares': 50}
]
```

**Execution layer** handles:
- Order routing to broker
- Order type selection (market vs limit)
- Execution timing
- Fill reporting

## Performance Metrics

Track portfolio management effectiveness:

**Allocation Metrics**:
- Number of positions held (avg, min, max)
- Cash buffer utilization (avg % cash)
- Position concentration (Herfindahl index)
- Turnover rate (% portfolio traded per rebalance)

**Performance Metrics**:
- Sharpe ratio (risk-adjusted return)
- Maximum drawdown
- Win rate (% profitable positions)
- Transaction cost impact

**Comparison Baseline**:
- Benchmark 1: Equal-weight all signals > threshold
- Benchmark 2: Buy-and-hold SPY
- Measure improvement from Phase 1 → Phase 2 → Phase 3

## Error Handling and Edge Cases

**Edge Case 1: No Strong Signals**
```python
if not strong_signals:
    return {'Cash': 1.0}  # Stay in cash
```

**Edge Case 2: All Signals Below Threshold**
```python
# Graceful degradation: hold current positions, don't force trades
```

**Edge Case 3: Insufficient Cash for Orders**
```python
# Rebalancer prioritizes sells before buys
# Or scales down all orders proportionally
```

**Edge Case 4: Price Data Missing**
```python
# Skip that security for this rebalance
# Log warning for investigation
```

**Edge Case 5: Extreme Signal Concentration**
```python
# All signals point to same sector → hit sector limits
# Cash buffer increases, or distribute across fewer positions
```

## Testing Strategy

**Unit Tests**:
- Test allocation logic with synthetic signals
- Test edge cases (no signals, all negative, extreme values)
- Test rebalancer math (current → target → orders)

**Integration Tests**:
- Full pipeline: signals → weights → orders
- Verify weights sum to 1.0
- Verify orders match weight differences

**Backtest Validation**:
- Compare Phase 1 simple allocation vs equal-weight benchmark
- Measure turnover and transaction costs
- Validate that system actually rebalances as expected

## Related Documents

- [strategy-layer-design.md](strategy-layer-design.md) - Signal semantics and generation
- [risk-management-design.md](risk-management-design.md) - Risk constraints on allocations (TBD)
- [execution-layer-design.md](execution-layer-design.md) - Order execution (TBD)
- [tech-stack.md](tech-stack.md) - Technology decisions

## Next Steps

1. ✅ Portfolio Management Layer design complete
2. ⏳ Discuss Risk Management Layer (validation and constraints)
3. ⏳ Discuss Execution Layer (broker integration, order types)
4. ⏳ Discuss Backtesting framework integration
5. ⏳ Implement Phase 1 Portfolio Manager
