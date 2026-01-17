# Risk Management Layer Design

**Status**: ✅ Decided (2026-01-17)

## Overview

The Risk Management Layer is the **safety guardian** of the trading system. Its primary purpose is to prevent catastrophic losses by setting boundaries and enforcing protective rules. While the Portfolio Management Layer optimizes for returns, the Risk Management Layer ensures we don't blow up the account in pursuit of those returns.

**Core Philosophy**: "First, do no harm. Preserve capital above all else."

## Risk Management vs Portfolio Management

It's important to distinguish these two layers:

| Aspect | Portfolio Management | Risk Management |
|--------|---------------------|-----------------|
| **Goal** | Maximize risk-adjusted returns | Prevent catastrophic losses |
| **Question** | "How to allocate optimally?" | "When to say NO?" |
| **Timing** | Proactive (optimization) | Reactive (validation & monitoring) |
| **Mindset** | Opportunity seeking | Risk avoiding |
| **Failure Mode** | Suboptimal returns | Account blow-up |

**Example**:
- Portfolio Layer: "Allocate 25% to AAPL based on strong signal"
- Risk Layer: "REJECT - single position limit is 20%"

## Core Responsibilities

The Risk Management Layer has three main functions:

### 1. Pre-Trade Risk Checks (Static Validation)

**When**: After Portfolio Layer generates target weights, before Execution Layer places orders

**What**: Validate that the proposed portfolio configuration complies with risk rules

**Checks**:
- Single position size limits (e.g., no stock > 20% of portfolio)
- Total exposure limits (e.g., max 90% invested)
- Minimum cash reserves (e.g., always keep 5%+ cash)
- Sector concentration limits (Phase 2+)
- Leverage/margin limits

**Action**: Approve, reject, or auto-adjust the proposed allocation

### 2. Position-Level Risk Management (Dynamic Monitoring)

**When**: Continuously during holding period (daily checks)

**What**: Monitor existing positions and trigger protective exits

**Mechanisms**:
- **Stop-loss**: Exit if position loses more than X% (e.g., -8%)
- **Take-profit**: Exit (partially or fully) if position gains more than Y% (e.g., +25%)
- **Trailing stop**: Exit if position drops X% from its peak (e.g., -5% from high)
- **Time-based exit**: Exit if position held for N days without progress

**Action**: Generate exit orders to Execution Layer

### 3. Portfolio-Level Risk Management (System Protection)

**When**: Daily/periodic monitoring of entire portfolio

**What**: Protect against systemic risk and drawdowns

**Mechanisms**:
- **Maximum drawdown protection**: Reduce exposure if portfolio drops X% from peak (e.g., 15%)
- **Circuit breaker**: Halt trading if single-day loss exceeds threshold (e.g., -5%)
- **Consecutive loss protection**: Reduce exposure after N consecutive losing days
- **Volatility regime detection**: Increase cash in high-volatility environments

**Action**: Reduce exposure, halt new positions, or pause trading entirely

## Available Tools and Libraries

### Why No Complete Library?

Like Portfolio Management, risk management is **highly personalized**. Different traders have different risk tolerances, time horizons, and constraints. Therefore, there's no one-size-fits-all library.

### Tool 1: QuantStats ⭐ Primary Recommendation

**Purpose**: Calculate risk metrics and generate risk reports

**What It Provides**:
- Risk metrics: Sharpe ratio, Sortino ratio, Max Drawdown, VaR, CVaR
- Performance analysis: Win rate, profit factor, recovery time
- HTML report generation

**What It Doesn't Provide**:
- Real-time risk checking
- Rule enforcement
- Order generation

**Installation**:
```bash
pip install quantstats
```

**Usage Example**:
```python
import quantstats as qs

# Calculate risk metrics
sharpe = qs.stats.sharpe(returns)
max_dd = qs.stats.max_drawdown(portfolio_values)
var_95 = qs.stats.value_at_risk(returns, confidence=0.95)
cvar_95 = qs.stats.cvar(returns, confidence=0.95)

# Generate comprehensive HTML report
qs.reports.html(returns,
               benchmark=spy_returns,
               output='risk_report.html',
               title='AI Trader Risk Report')
```

**Use Cases**:
- Phase 2-3: Portfolio-level health monitoring
- Post-trade analysis and reporting
- Backtesting performance evaluation

### Tool 2: PyPortfolioOpt ⚠️ Limited Use

**Purpose**: Optimization with constraints (not standalone risk management)

**What It Provides**:
- Add constraints during portfolio optimization (max weight, sector limits)

**Limitation**: Only works during optimization phase, not for real-time monitoring

**Use Case**: Phase 3, when using optimization in Portfolio Layer

### Tool 3: empyrical (Alternative to QuantStats)

**Purpose**: Financial metrics calculation (Quantopian legacy)

**Pros**: More low-level control
**Cons**: Less user-friendly than QuantStats, requires more manual work

**Installation**:
```bash
pip install empyrical
```

### Our Approach: Custom Implementation + QuantStats

**Decision**:
- **Core risk logic**: Custom implementation (rules, checks, triggers)
- **Risk metrics**: QuantStats (Sharpe, Drawdown, VaR, reports)
- **Constraints in optimization**: PyPortfolioOpt (Phase 3 only)

## Progressive Implementation Plan

### Phase 1: Basic Static Risk Checks (IMMEDIATE)

**Objective**: Prevent obvious configuration errors before execution

**Scope**: Pre-trade validation only

**Implementation**:

```python
from typing import Dict, Tuple

class BasicRiskManager:
    """
    Phase 1: Simple pre-trade validation.

    Validates proposed portfolio allocations against basic risk rules.
    Uses Mode B: Auto-adjustment (modify weights to comply with rules).
    """

    def __init__(self, config: Dict):
        """
        Initialize with risk parameters.

        Args:
            config: {
                'max_position_size': 0.20,   # Single stock max 20%
                'max_total_exposure': 0.90,  # Max 90% invested
                'min_cash_reserve': 0.05,    # Min 5% cash
            }
        """
        self.max_position_size = config.get('max_position_size', 0.20)
        self.max_total_exposure = config.get('max_exposure', 0.90)
        self.min_cash_reserve = config.get('min_cash', 0.05)

    def validate_weights(self,
                        target_weights: Dict[str, float]) -> Tuple[bool, str, Dict]:
        """
        Validate proposed portfolio weights.

        Args:
            target_weights: {symbol: weight} from Portfolio Layer
                           Weights should sum to 1.0

        Returns:
            (is_valid, message, adjusted_weights)
            - is_valid: True if passed all checks (possibly after adjustment)
            - message: Description of checks/adjustments
            - adjusted_weights: Modified weights (may be same as input)
        """
        adjusted_weights = target_weights.copy()
        adjustments = []

        # Check 1: Single position size limits
        violations = []
        for symbol, weight in adjusted_weights.items():
            if symbol == 'Cash':
                continue

            if weight > self.max_position_size:
                violations.append((symbol, weight))

        if violations:
            # Auto-adjust: cap at max and redistribute excess to cash
            for symbol, weight in violations:
                excess = weight - self.max_position_size
                adjusted_weights[symbol] = self.max_position_size
                adjusted_weights['Cash'] = adjusted_weights.get('Cash', 0) + excess

            adjustments.append(
                f"Capped {len(violations)} position(s) at {self.max_position_size:.0%}"
            )

        # Check 2: Total exposure limit
        total_exposure = sum(w for s, w in adjusted_weights.items() if s != 'Cash')

        if total_exposure > self.max_total_exposure:
            # Scale down all positions proportionally
            scale_factor = self.max_total_exposure / total_exposure

            for symbol in adjusted_weights:
                if symbol != 'Cash':
                    adjusted_weights[symbol] *= scale_factor

            # Recalculate cash
            adjusted_weights['Cash'] = 1.0 - sum(
                w for s, w in adjusted_weights.items() if s != 'Cash'
            )

            adjustments.append(
                f"Scaled exposure from {total_exposure:.0%} to {self.max_total_exposure:.0%}"
            )

        # Check 3: Minimum cash reserve
        cash = adjusted_weights.get('Cash', 0)

        if cash < self.min_cash_reserve:
            # Scale down positions to free up cash
            shortage = self.min_cash_reserve - cash
            current_invested = sum(w for s, w in adjusted_weights.items() if s != 'Cash')

            if current_invested > 0:
                scale_factor = (current_invested - shortage) / current_invested

                for symbol in adjusted_weights:
                    if symbol != 'Cash':
                        adjusted_weights[symbol] *= scale_factor

                adjusted_weights['Cash'] = self.min_cash_reserve

                adjustments.append(
                    f"Increased cash reserve to {self.min_cash_reserve:.0%}"
                )

        # Ensure weights still sum to 1.0 (handle rounding errors)
        total = sum(adjusted_weights.values())
        if abs(total - 1.0) > 1e-6:
            # Adjust cash to make it exact
            adjusted_weights['Cash'] += (1.0 - total)

        # Generate message
        if not adjustments:
            message = "All risk checks passed"
        else:
            message = "Risk adjustments: " + "; ".join(adjustments)

        return (True, message, adjusted_weights)


# Integration example
class RiskManagerIntegration:
    """
    Example of how Risk Manager integrates into the trading flow.
    """

    def daily_rebalance_with_risk_checks(self,
                                         signals: Dict[str, float],
                                         portfolio_manager,
                                         risk_manager: BasicRiskManager,
                                         current_portfolio: Dict,
                                         prices: Dict[str, float]):
        """
        Complete rebalancing flow with risk validation.
        """
        # Step 1: Portfolio Layer generates target weights
        target_weights = portfolio_manager.calculate_target_weights(signals)

        print(f"Portfolio Layer proposed: {target_weights}")

        # Step 2: Risk Layer validates and potentially adjusts
        is_valid, message, adjusted_weights = risk_manager.validate_weights(target_weights)

        print(f"Risk Manager: {message}")

        if adjusted_weights != target_weights:
            print(f"Adjusted weights: {adjusted_weights}")

        # Step 3: Generate orders based on adjusted weights
        orders = portfolio_manager.generate_orders(
            adjusted_weights,
            current_portfolio,
            prices
        )

        # Step 4: Send to Execution Layer
        return orders
```

**Configuration Example**:
```yaml
risk_management:
  phase: 1  # Basic static checks only

  # Position limits
  max_position_size: 0.20   # Single stock max 20%
  max_total_exposure: 0.90  # Max 90% invested
  min_cash_reserve: 0.05    # Always keep 5%+ cash
```

**Testing**:
```python
# Test case: Portfolio wants 30% in AAPL
config = {
    'max_position_size': 0.20,
    'max_exposure': 0.90,
    'min_cash': 0.05
}

risk_mgr = BasicRiskManager(config)

# Proposed allocation
target = {
    'AAPL': 0.30,  # Exceeds 20% limit!
    'MSFT': 0.15,
    'GOOGL': 0.10,
    'Cash': 0.45
}

is_valid, msg, adjusted = risk_mgr.validate_weights(target)

print(msg)  # "Risk adjustments: Capped 1 position(s) at 20%"
print(adjusted)  # {'AAPL': 0.20, 'MSFT': 0.15, 'GOOGL': 0.10, 'Cash': 0.55}
```

**Why Mode B (Auto-Adjustment)?**
- **For Phase 1 (backtesting)**: Automatic is fine, we want the system to run without manual intervention
- **Logging**: All adjustments are logged for analysis
- **For live trading**: Can upgrade to Mode C (alert + manual approval) later

### Phase 2: Dynamic Stop-Loss & Take-Profit (MID-TERM)

**Objective**: Protect running positions from large losses and lock in gains

**Scope**: Position-level monitoring during holding period

**Implementation**:

```python
from datetime import datetime
from typing import List, Dict

class DynamicRiskManager(BasicRiskManager):
    """
    Phase 2: Add dynamic position monitoring with stop-loss/take-profit.

    Monitors positions daily and generates exit orders when risk thresholds are breached.
    """

    def __init__(self, config: Dict):
        super().__init__(config)

        # Stop-loss and take-profit parameters
        self.stop_loss_pct = config.get('stop_loss', 0.08)         # -8%
        self.take_profit_pct = config.get('take_profit', 0.25)     # +25%
        self.trailing_stop_pct = config.get('trailing_stop', 0.05) # -5% from peak

        # Time-based exit
        self.max_holding_days = config.get('max_holding_days', None)  # Optional

    def check_position_exits(self,
                            positions: Dict[str, Dict],
                            current_prices: Dict[str, float]) -> List[Dict]:
        """
        Check if any positions should be exited due to stop-loss or take-profit.

        Args:
            positions: {
                'AAPL': {
                    'shares': 100,
                    'entry_price': 150.00,
                    'entry_date': '2024-01-15',
                    'peak_price': 165.00,  # Tracked for trailing stop
                },
                ...
            }
            current_prices: {'AAPL': 155.50, ...}

        Returns:
            List of exit orders:
            [
                {
                    'action': 'SELL',
                    'symbol': 'AAPL',
                    'shares': 100,
                    'reason': 'Stop-loss triggered (-8.2%)'
                },
                ...
            ]
        """
        exit_orders = []

        for symbol, position in positions.items():
            current_price = current_prices.get(symbol)

            if current_price is None:
                # No price data, skip (log warning in production)
                continue

            entry_price = position['entry_price']
            shares = position['shares']
            peak_price = position.get('peak_price', entry_price)

            # Update peak price (for trailing stop)
            if current_price > peak_price:
                position['peak_price'] = current_price
                peak_price = current_price

            # Calculate P&L
            pnl_pct = (current_price - entry_price) / entry_price

            # Check 1: Stop-loss
            if pnl_pct < -self.stop_loss_pct:
                exit_orders.append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'shares': shares,
                    'reason': f'Stop-loss triggered ({pnl_pct:.1%})',
                    'price': current_price
                })
                continue  # Only one exit reason per position

            # Check 2: Take-profit
            if pnl_pct > self.take_profit_pct:
                exit_orders.append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'shares': shares,
                    'reason': f'Take-profit triggered ({pnl_pct:.1%})',
                    'price': current_price
                })
                continue

            # Check 3: Trailing stop
            drawdown_from_peak = (current_price - peak_price) / peak_price

            if drawdown_from_peak < -self.trailing_stop_pct:
                exit_orders.append({
                    'action': 'SELL',
                    'symbol': symbol,
                    'shares': shares,
                    'reason': f'Trailing stop ({drawdown_from_peak:.1%} from peak ${peak_price:.2f})',
                    'price': current_price
                })
                continue

            # Check 4: Time-based exit (optional)
            if self.max_holding_days:
                entry_date = datetime.strptime(position['entry_date'], '%Y-%m-%d')
                days_held = (datetime.now() - entry_date).days

                if days_held > self.max_holding_days:
                    exit_orders.append({
                        'action': 'SELL',
                        'symbol': symbol,
                        'shares': shares,
                        'reason': f'Time-based exit ({days_held} days held)',
                        'price': current_price
                    })

        return exit_orders


# Daily execution flow with dynamic risk checks
def daily_trading_flow_phase2(signals, positions, prices,
                              portfolio_mgr, risk_mgr: DynamicRiskManager):
    """
    Phase 2 daily flow: Check exits BEFORE rebalancing.
    """
    print("=== Daily Risk Checks ===")

    # Step 1: Check for position exits (stop-loss, take-profit, etc.)
    exit_orders = risk_mgr.check_position_exits(positions, prices)

    if exit_orders:
        print(f"Risk-triggered exits: {len(exit_orders)}")
        for order in exit_orders:
            print(f"  EXIT {order['symbol']}: {order['reason']}")

        # Execute exits (send to Execution Layer)
        execute_orders(exit_orders)

        # Update positions after exits
        positions = update_positions_after_orders(positions, exit_orders)
    else:
        print("No risk-triggered exits")

    # Step 2: Normal rebalancing (if scheduled)
    if should_rebalance_today():
        print("\n=== Rebalancing ===")

        # Generate target weights
        target_weights = portfolio_mgr.calculate_target_weights(signals)

        # Validate with static risk checks
        is_valid, msg, adjusted_weights = risk_mgr.validate_weights(target_weights)
        print(f"Risk validation: {msg}")

        # Generate rebalancing orders
        rebalance_orders = portfolio_mgr.generate_orders(
            adjusted_weights, positions, prices
        )

        # Execute
        execute_orders(rebalance_orders)
```

**Configuration**:
```yaml
risk_management:
  phase: 2  # Static + Dynamic

  # Static checks (from Phase 1)
  max_position_size: 0.20
  max_total_exposure: 0.90
  min_cash_reserve: 0.05

  # Dynamic position monitoring
  stop_loss: 0.08          # Exit if position down 8%
  take_profit: 0.25        # Exit if position up 25%
  trailing_stop: 0.05      # Exit if down 5% from peak
  max_holding_days: null   # Optional: max days to hold (null = no limit)
```

**Key Design Choice: Stop-Loss in Risk Layer, Not Strategy Layer**

**Rationale**:
- **Technical stop-loss** (like -8%) is a **protective mechanism**, not strategy logic
- Even if strategy signal remains bullish, we exit if loss threshold is breached
- Strategy Layer can still generate its own exits via signal changes (e.g., MA death cross)
- Two independent exit mechanisms:
  1. **Strategy exit**: Signal drops below threshold → natural exit via rebalancing
  2. **Risk exit**: Loss limit hit → forced exit regardless of signal

**Example**:
```
Day 1: Buy AAPL at $150 (signal = 0.8)
Day 5: Price drops to $138 (signal still 0.7, strategy still bullish)
        → Risk Layer triggers stop-loss at -8% → EXIT
        → Strategy Layer would have held (signal > 0.3)
        → Risk Layer overrides strategy to protect capital
```

### Phase 3: Portfolio-Level Risk & VaR Monitoring (ADVANCED)

**Objective**: System-wide risk management and stress testing

**Scope**: Entire portfolio health monitoring

**Implementation**:

```python
import quantstats as qs
import pandas as pd
import numpy as np

class AdvancedRiskManager(DynamicRiskManager):
    """
    Phase 3: Portfolio-level risk management with VaR/CVaR and drawdown protection.

    Uses QuantStats for professional risk metrics calculation.
    """

    def __init__(self, config: Dict):
        super().__init__(config)

        # Portfolio-level thresholds
        self.max_drawdown_threshold = config.get('max_drawdown', 0.15)      # 15%
        self.circuit_breaker_loss = config.get('circuit_breaker', 0.05)     # 5% daily
        self.consecutive_loss_days = config.get('consecutive_loss_days', 5) # 5 days

        # VaR parameters
        self.var_confidence = config.get('var_confidence', 0.95)  # 95% VaR

    def check_portfolio_health(self,
                              portfolio_values: pd.Series,
                              returns: pd.Series = None) -> Dict:
        """
        Assess overall portfolio health using risk metrics.

        Args:
            portfolio_values: Series of daily portfolio values (indexed by date)
            returns: Series of daily returns (optional, will calculate if not provided)

        Returns:
            {
                'action': 'continue' | 'reduce_exposure' | 'halt_trading',
                'reason': str,
                'metrics': {risk metrics},
                'recommended_exposure': float (if action != 'continue')
            }
        """
        if returns is None:
            returns = portfolio_values.pct_change().dropna()

        # Calculate risk metrics using QuantStats
        metrics = {
            'current_drawdown': qs.stats.max_drawdown(portfolio_values),
            'sharpe_ratio': qs.stats.sharpe(returns) if len(returns) > 0 else 0,
            'sortino_ratio': qs.stats.sortino(returns) if len(returns) > 0 else 0,
            'var_95': qs.stats.value_at_risk(returns, confidence=self.var_confidence) if len(returns) > 30 else None,
            'cvar_95': qs.stats.cvar(returns, confidence=self.var_confidence) if len(returns) > 30 else None,
            'volatility': qs.stats.volatility(returns) if len(returns) > 0 else 0,
        }

        # Check 1: Maximum drawdown breached
        current_dd = abs(metrics['current_drawdown'])
        if current_dd > self.max_drawdown_threshold:
            return {
                'action': 'reduce_exposure',
                'reason': f'Drawdown {current_dd:.1%} exceeds limit {self.max_drawdown_threshold:.1%}',
                'metrics': metrics,
                'recommended_exposure': 0.50  # Reduce to 50% invested
            }

        # Check 2: Circuit breaker (single-day catastrophic loss)
        if len(returns) > 0:
            last_day_return = returns.iloc[-1]

            if last_day_return < -self.circuit_breaker_loss:
                return {
                    'action': 'halt_trading',
                    'reason': f'Circuit breaker: Daily loss {last_day_return:.1%}',
                    'metrics': metrics
                }

        # Check 3: Consecutive losing days
        if len(returns) >= self.consecutive_loss_days:
            recent_returns = returns.tail(self.consecutive_loss_days)

            if (recent_returns < 0).all():
                return {
                    'action': 'reduce_exposure',
                    'reason': f'{self.consecutive_loss_days} consecutive losing days',
                    'metrics': metrics,
                    'recommended_exposure': 0.70  # Reduce to 70%
                }

        # All checks passed
        return {
            'action': 'continue',
            'reason': 'Portfolio within risk parameters',
            'metrics': metrics
        }

    def generate_risk_report(self,
                            returns: pd.Series,
                            benchmark_returns: pd.Series = None,
                            output_path: str = 'risk_report.html'):
        """
        Generate comprehensive risk report using QuantStats.

        Args:
            returns: Portfolio returns series
            benchmark_returns: Benchmark (e.g., SPY) returns for comparison
            output_path: Where to save HTML report
        """
        qs.reports.html(
            returns,
            benchmark=benchmark_returns,
            output=output_path,
            title='AI Trader Risk & Performance Report'
        )

        print(f"Risk report generated: {output_path}")

        # Also print key metrics to console
        print("\n=== Key Risk Metrics ===")
        print(f"Sharpe Ratio: {qs.stats.sharpe(returns):.2f}")
        print(f"Sortino Ratio: {qs.stats.sortino(returns):.2f}")
        print(f"Max Drawdown: {qs.stats.max_drawdown(returns):.1%}")
        print(f"Volatility (Ann.): {qs.stats.volatility(returns):.1%}")

        if len(returns) > 30:
            print(f"VaR (95%): {qs.stats.value_at_risk(returns):.1%}")
            print(f"CVaR (95%): {qs.stats.cvar(returns):.1%}")
```

**Daily Monitoring Flow**:
```python
def daily_flow_phase3(portfolio_values, returns, positions, signals, prices,
                     portfolio_mgr, risk_mgr: AdvancedRiskManager):
    """
    Phase 3: Complete risk monitoring including portfolio-level checks.
    """
    # Step 1: Portfolio-level health check
    health = risk_mgr.check_portfolio_health(portfolio_values, returns)

    print(f"Portfolio Health: {health['action']} - {health['reason']}")
    print(f"Metrics: Sharpe={health['metrics']['sharpe_ratio']:.2f}, "
          f"DD={health['metrics']['current_drawdown']:.1%}")

    if health['action'] == 'halt_trading':
        print("TRADING HALTED - Manual review required")
        return  # Stop all trading

    if health['action'] == 'reduce_exposure':
        # Override portfolio allocation to reduce risk
        recommended_exposure = health['recommended_exposure']
        print(f"Reducing exposure to {recommended_exposure:.0%}")

        # Force cash increase
        # (Implementation: scale down all target weights)

    # Step 2: Position-level exits (stop-loss, etc.)
    exit_orders = risk_mgr.check_position_exits(positions, prices)
    if exit_orders:
        execute_orders(exit_orders)
        positions = update_positions(positions, exit_orders)

    # Step 3: Normal rebalancing (if allowed)
    if health['action'] == 'continue' and should_rebalance_today():
        # ... standard rebalancing flow ...
        pass
```

**Configuration**:
```yaml
risk_management:
  phase: 3  # Full risk management

  # Static (Phase 1)
  max_position_size: 0.20
  max_total_exposure: 0.90
  min_cash_reserve: 0.05

  # Dynamic (Phase 2)
  stop_loss: 0.08
  take_profit: 0.25
  trailing_stop: 0.05

  # Portfolio-level (Phase 3)
  max_drawdown: 0.15         # 15% max drawdown
  circuit_breaker: 0.05      # Halt if -5% in single day
  consecutive_loss_days: 5   # Reduce after 5 losing days
  var_confidence: 0.95       # 95% VaR
```

**Dependencies**:
```bash
pip install quantstats
```

## Architecture Decision: Independent Layer

**Decision**: Risk Management is a **standalone layer** between Portfolio Management and Execution

```
Data Layer
    ↓
Strategy Layer (signals)
    ↓
Portfolio Management Layer (target weights)
    ↓
Risk Management Layer (validation & monitoring)  ← Independent layer
    ↓
Execution Layer (orders)
```

**Rationale**:
- ✅ Clear separation of concerns (optimization vs safety)
- ✅ Easy to test and debug in isolation
- ✅ Can evolve independently (Phase 1 → 2 → 3)
- ✅ Reusable across different portfolio strategies

**Alternative (Rejected)**: Integrate into Portfolio Layer
- ❌ Conflates two different responsibilities
- ❌ Harder to reason about and maintain
- ❌ PyPortfolioOpt constraints are not sufficient for full risk management

## Key Design Decisions

### Decision 1: Stop-Loss Ownership

**Question**: Should stop-loss be in Strategy Layer or Risk Layer?

**Answer**: **Risk Layer** ✅

**Two Types of Exits**:

1. **Strategy-driven exit**:
   - Cause: Signal drops below threshold (e.g., MA death cross)
   - Owner: Strategy Layer
   - Mechanism: Signal changes → Portfolio rebalancing

2. **Risk-driven exit**:
   - Cause: Loss limit breached (e.g., -8%)
   - Owner: Risk Layer
   - Mechanism: Stop-loss trigger → Forced exit order

**Both can happen independently**:
- Risk stop-loss can trigger even if strategy signal is still bullish
- Strategy exit can happen even if risk limits aren't hit

### Decision 2: Enforcement Mode

**Question**: Should risk violations be hard-rejected or auto-adjusted?

**Answer**: **Mode B - Auto-Adjustment** ✅ (for Phase 1-2)

**Three Modes**:

**Mode A: Hard Rejection** ⚠️
```python
if not compliant:
    raise RiskViolationError("REJECTED")
```
- Too rigid, system stops on violation
- Good for: Production with human oversight

**Mode B: Auto-Adjustment** ✅ **SELECTED**
```python
if not compliant:
    adjusted = auto_fix_to_comply(weights)
    return adjusted
```
- System keeps running, logs adjustments
- Good for: Backtesting, automated systems

**Mode C: Alert + Manual Approval**
```python
if not compliant:
    send_alert_to_trader()
    wait_for_approval()
```
- Human in the loop
- Good for: Live trading with real money

**Our Choice for Now**: Mode B
- **Reason**: Phase 1 is backtesting, need automation
- **Future**: Can switch to Mode C when going live

### Decision 3: Risk Metrics Calculation

**Question**: Build our own or use library?

**Answer**: **Use QuantStats** ✅

**Rationale**:
- Sharpe, Sortino, VaR, CVaR are complex to calculate correctly
- QuantStats is battle-tested and widely used
- Provides HTML reports (useful for analysis)
- No need to reinvent the wheel

**What We Build**:
- Rule enforcement logic (position limits, stop-loss triggers)
- Integration with Portfolio and Execution layers

**What We Use**:
- QuantStats for metrics (Sharpe, Drawdown, VaR)

## Error Handling and Edge Cases

**Edge Case 1: No price data available**
```python
if symbol not in current_prices:
    logger.warning(f"No price for {symbol}, skipping risk check")
    continue
```

**Edge Case 2: Position data incomplete**
```python
if 'entry_price' not in position:
    logger.error(f"Missing entry_price for {symbol}")
    # Use current price as entry (conservative)
    position['entry_price'] = current_prices[symbol]
```

**Edge Case 3: Weights don't sum to 1.0 (rounding)**
```python
total = sum(weights.values())
if abs(total - 1.0) > 1e-6:
    # Adjust cash to compensate
    weights['Cash'] += (1.0 - total)
```

**Edge Case 4: All positions hit stop-loss**
```python
if all_positions_exited:
    # Perfectly fine - go to 100% cash
    # Wait for new signals
```

## Testing Strategy

**Unit Tests**:
- Test each risk check in isolation
- Test auto-adjustment logic
- Test stop-loss calculations

**Integration Tests**:
- Full flow: Portfolio → Risk → adjusted weights
- Verify risk layer correctly modifies violations

**Backtesting Validation**:
- Compare Phase 1 (with risk) vs No Risk
- Verify max drawdown is actually limited
- Verify stop-losses trigger correctly

## Performance Metrics

Track risk layer effectiveness:

**Protection Metrics**:
- Max drawdown achieved vs threshold
- Number of stop-losses triggered
- Number of take-profits triggered
- Circuit breaker activations

**Cost Metrics**:
- Returns lost due to stop-losses (false exits)
- Opportunity cost of position limits
- Impact on Sharpe ratio

**Trade-off Analysis**:
- Risk-adjusted returns with vs without risk layer

## Related Documents

- [portfolio-management-design.md](portfolio-management-design.md) - Portfolio allocation layer
- [strategy-layer-design.md](strategy-layer-design.md) - Signal generation
- [execution-layer-design.md](execution-layer-design.md) - Order execution (TBD)
- [tech-stack.md](tech-stack.md) - Technology decisions

## Next Steps

1. ✅ Risk Management Layer design complete
2. ⏳ Discuss Execution Layer (broker APIs, order types)
3. ⏳ Discuss Backtesting framework integration
4. ⏳ Implement Phase 1 Risk Manager
5. ⏳ Finalize overall architecture diagram
