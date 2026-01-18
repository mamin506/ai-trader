# System Safety Design

## Overview

Safety is the paramount requirement for an automated trading system. This document defines the **Fail-Safe** mechanisms and **Risk Control** principles designed to protect capital and ensuring operational integrity when errors occur.

## Core Principles

1.  **Fail-Safe Defaults**: When in doubt or when data is missing, the system defaults to the safest action (typically **Hold/Do Nothing**), never to a random or aggressive action.
2.  **Harm Minimization**: The primary goal during an anomaly is to prevent *new* bad trades, rather than forcing an exit from existing trades (which might crystallize losses based on bad data).
3.  **Human-in-the-Loop**: Critical errors trigger alerts that pause automation, requiring human intervention to resume. The system acknowledges its limits.
4.  **Defense in Depth**: Safety checks exist at multiple layers (Data, Strategy, Execution), ensuring that a failure in one layer is caught by the next.

## Data Safety Layer

The first line of defense is ensuring decision-making is based on valid data.

### 1. Data Validation (The Gatekeeper)
Before any data enters the Strategy Layer, it must pass strict validation checks.

*   **Completeness**:
    *   Check against **Trading Calendar** (via provider or `exchange_calendars`).
    *   Verify no missing trading days in the requested range.
    *   Verify no missing columns (OHLCV).
*   **Integrity**:
    *   Price > 0.
    *   High >= max(Open, Close).
    *   Low <= min(Open, Close).
    *   Volume >= 0.
*   **Anomaly Detection** (Warnings):
    *   **Spike Detection**: Alert if price moves > `N * Volatility` (e.g., 5-sigma event) or a static threshold (e.g., 20% for large caps) in a single day.
    *   **Stale Data**: Alert if price/volume remains exactly identical for extended periods.

### 2. Handling Invalid Data
If validation fails:
1.  **Block**: The specific symbol is marked as `INVALID`.
2.  **Isolate**: It is excluded from the Strategy Layer's calculation set.
3.  **Alert**: A `DataQualityError` is logged, and an operator alert is triggered.

## Execution Safety Layer

How the system behaves when data is invalid or missing, especially for existing positions.

### 1. The "Holding" Scenario
If the system holds a position in `AAPL`, but today's data for `AAPL` is invalid/missing:

*   **Risk**: Selling on bad data (e.g., price=0) causes catastrophic loss. Buying on bad data (e.g., price spike) buys at the top.
*   **Protocol**: **FREEZE & HOLD**.
    *   **Action**: Do NOT generate any Sell/Buy signals.
    *   **State**: Maintain current position.
    *   **Notification**: "Data Error on Held Asset [AAPL] - Automation Paused for this asset."
*   **Rationale**: In the absence of reliable information, maintaining the status quo is statistically safer than taking active measures ("do no harm").

### 2. Strategy Output Safety
*   **No Signal vs. Neutral Signal**:
    *   `None` (Error): Data missing/invalid. **Action**: Hold/Freeze.
    *   `0` (Neutral): Data valid, but strategy says don't trade. **Action**: Risk management decides (e.g., close if time expired) or Hold.

## Operational Safety

### 1. Circuit Breakers
*   **Market-Wide**: If major indices (SPY) drop > 7% (Level 1 Breaker), pause all buying activities.
*   **System-Wide**: If data provider error rate > 10%, pause **entire system**.

### 2. Manual Override (Kill Switch)
*   A "Panic Button" feature to:
    1.  Cancel all open orders immediately.
    2.  (Optional) Liquidate all positions (Extreme case).
    3.  Disable all scheduler jobs.

## Summary of Failure Modes

| Failure Scenario | System Response | Human Action |
| :--- | :--- | :--- |
| **API Down / Network Fail** | Retry -> Fail -> **Hold All** | Check internet/provider status |
| **Data Validation Fail (Single Asset)** | Exclude Asset -> **Hold Position** | Review asset manualy |
| **Strategy Crash** | Catch Exception -> **Hold All** | Fix bug, restart service |
| **Order Rejection** | Log Error -> **Stop Retrying** | Check broker account/margin |

## Related Documents
*   [data-layer-design.md](data-layer-design.md) - Details on DataProvider interface.
*   [risk-management-design.md](risk-management-design.md) - Position sizing and stop-loss rules.
