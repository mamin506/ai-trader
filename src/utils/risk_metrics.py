"""Risk Metrics Utilities.

This module provides advanced risk metrics calculations beyond basic Sharpe ratio.
"""

import numpy as np
import pandas as pd
from typing import Optional


def calculate_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """Calculate Sortino Ratio (downside risk-adjusted return).

    Sortino ratio only penalizes downside volatility, unlike Sharpe which
    penalizes all volatility (including upside).

    Args:
        returns: Series of periodic returns
        risk_free_rate: Annual risk-free rate (default: 0)
        periods_per_year: Number of periods per year (default: 252 for daily)

    Returns:
        Sortino ratio, or None if insufficient data
    """
    if len(returns) < 2:
        return None

    # Calculate excess returns
    excess_returns = returns - (risk_free_rate / periods_per_year)

    # Calculate downside deviation (only negative returns)
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0:
        return None  # No downside risk

    downside_std = downside_returns.std()

    if downside_std == 0:
        return None

    # Annualize
    sortino = (excess_returns.mean() / downside_std) * np.sqrt(periods_per_year)

    return float(sortino)


def calculate_calmar_ratio(
    annualized_return: float,
    max_drawdown: float,
) -> Optional[float]:
    """Calculate Calmar Ratio (return / max drawdown).

    Args:
        annualized_return: Annualized return (as decimal, e.g., 0.15 for 15%)
        max_drawdown: Maximum drawdown (as decimal, e.g., 0.10 for 10%)

    Returns:
        Calmar ratio, or None if max_drawdown is 0
    """
    if max_drawdown == 0:
        return None

    return annualized_return / max_drawdown


def calculate_var(
    returns: pd.Series,
    confidence_level: float = 0.95,
) -> float:
    """Calculate Value at Risk (VaR).

    VaR estimates the maximum loss at a given confidence level.

    Args:
        returns: Series of periodic returns
        confidence_level: Confidence level (default: 0.95 for 95%)

    Returns:
        VaR as a positive number (e.g., 0.02 means 2% loss)
    """
    if len(returns) == 0:
        return 0.0

    # Calculate the percentile
    var = np.percentile(returns, (1 - confidence_level) * 100)

    # Return as positive number (loss)
    return float(abs(var))


def calculate_cvar(
    returns: pd.Series,
    confidence_level: float = 0.95,
) -> float:
    """Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

    CVaR is the average loss beyond VaR threshold.

    Args:
        returns: Series of periodic returns
        confidence_level: Confidence level (default: 0.95)

    Returns:
        CVaR as a positive number
    """
    if len(returns) == 0:
        return 0.0

    var = calculate_var(returns, confidence_level)

    # Calculate average of returns worse than VaR
    threshold = -var  # Negative because we're looking at losses
    tail_returns = returns[returns <= threshold]

    if len(tail_returns) == 0:
        return var  # If no tail, CVaR = VaR

    cvar = abs(tail_returns.mean())

    return float(cvar)


def calculate_omega_ratio(
    returns: pd.Series,
    threshold: float = 0.0,
) -> Optional[float]:
    """Calculate Omega Ratio (probability-weighted gains/losses).

    Omega ratio measures the probability-weighted ratio of gains to losses
    relative to a threshold return.

    Args:
        returns: Series of periodic returns
        threshold: Threshold return (default: 0 for zero return)

    Returns:
        Omega ratio, or None if no losses
    """
    if len(returns) == 0:
        return None

    gains = returns[returns > threshold] - threshold
    losses = threshold - returns[returns < threshold]

    if len(losses) == 0 or losses.sum() == 0:
        return None  # No losses, infinite Omega

    omega = gains.sum() / losses.sum()

    return float(omega)


def calculate_ulcer_index(
    equity_curve: pd.Series,
) -> float:
    """Calculate Ulcer Index (drawdown-based risk measure).

    Ulcer Index measures the depth and duration of drawdowns.
    Lower is better.

    Args:
        equity_curve: Series of portfolio values over time

    Returns:
        Ulcer Index (lower = less painful drawdowns)
    """
    if len(equity_curve) < 2:
        return 0.0

    # Calculate running maximum
    running_max = equity_curve.cummax()

    # Calculate percentage drawdowns
    drawdowns = (equity_curve - running_max) / running_max

    # Square each drawdown, take average, then square root
    ulcer = np.sqrt((drawdowns ** 2).mean())

    return float(ulcer)


def calculate_comprehensive_risk_metrics(
    returns: pd.Series,
    equity_curve: pd.Series,
    annualized_return: float,
    max_drawdown: float,
    risk_free_rate: float = 0.0,
) -> dict:
    """Calculate all risk metrics at once.

    Args:
        returns: Daily returns series
        equity_curve: Portfolio value series
        annualized_return: Annualized return
        max_drawdown: Maximum drawdown
        risk_free_rate: Annual risk-free rate

    Returns:
        Dict with all risk metrics
    """
    metrics = {
        # Existing
        'sharpe_ratio': None,
        'max_drawdown': max_drawdown,

        # Advanced
        'sortino_ratio': calculate_sortino_ratio(returns, risk_free_rate),
        'calmar_ratio': calculate_calmar_ratio(annualized_return, max_drawdown),
        'var_95': calculate_var(returns, 0.95),
        'cvar_95': calculate_cvar(returns, 0.95),
        'var_99': calculate_var(returns, 0.99),
        'omega_ratio': calculate_omega_ratio(returns),
        'ulcer_index': calculate_ulcer_index(equity_curve),
    }

    # Calculate Sharpe if enough data
    if len(returns) > 1:
        excess_returns = returns - (risk_free_rate / 252)
        if returns.std() > 0:
            metrics['sharpe_ratio'] = (excess_returns.mean() / returns.std()) * np.sqrt(252)

    return metrics


def assess_risk_level(metrics: dict) -> dict:
    """Assess overall risk level based on metrics.

    Args:
        metrics: Dict of risk metrics

    Returns:
        Dict with risk assessment and recommendations
    """
    risk_score = 0
    max_score = 100
    issues = []
    strengths = []

    # Sharpe Ratio (30 points)
    sharpe = metrics.get('sharpe_ratio')
    if sharpe is not None:
        if sharpe > 2.0:
            risk_score += 30
            strengths.append(f"Excellent Sharpe ratio ({sharpe:.2f})")
        elif sharpe > 1.0:
            risk_score += 20
            strengths.append(f"Good Sharpe ratio ({sharpe:.2f})")
        elif sharpe > 0.5:
            risk_score += 10
            issues.append(f"Marginal Sharpe ratio ({sharpe:.2f})")
        else:
            issues.append(f"Poor Sharpe ratio ({sharpe:.2f})")

    # Max Drawdown (25 points)
    max_dd = metrics.get('max_drawdown', 0)
    if max_dd < 0.10:
        risk_score += 25
        strengths.append(f"Low max drawdown ({max_dd*100:.1f}%)")
    elif max_dd < 0.20:
        risk_score += 15
        strengths.append(f"Acceptable max drawdown ({max_dd*100:.1f}%)")
    elif max_dd < 0.30:
        risk_score += 5
        issues.append(f"High max drawdown ({max_dd*100:.1f}%)")
    else:
        issues.append(f"Excessive max drawdown ({max_dd*100:.1f}%)")

    # Sortino Ratio (20 points)
    sortino = metrics.get('sortino_ratio')
    if sortino is not None:
        if sortino > 2.0:
            risk_score += 20
            strengths.append(f"Excellent Sortino ratio ({sortino:.2f})")
        elif sortino > 1.0:
            risk_score += 15
        elif sortino > 0.5:
            risk_score += 7

    # Calmar Ratio (15 points)
    calmar = metrics.get('calmar_ratio')
    if calmar is not None:
        if calmar > 3.0:
            risk_score += 15
            strengths.append(f"Excellent Calmar ratio ({calmar:.2f})")
        elif calmar > 2.0:
            risk_score += 10
        elif calmar > 1.0:
            risk_score += 5
        else:
            issues.append(f"Low Calmar ratio ({calmar:.2f})")

    # VaR (10 points)
    var_95 = metrics.get('var_95', 0)
    if var_95 < 0.02:
        risk_score += 10
        strengths.append(f"Low daily VaR ({var_95*100:.1f}%)")
    elif var_95 < 0.03:
        risk_score += 5

    # Determine risk level
    if risk_score >= 80:
        level = "Very Low Risk"
        recommendation = "Excellent risk profile - suitable for conservative investors"
    elif risk_score >= 60:
        level = "Low to Moderate Risk"
        recommendation = "Good risk profile - suitable for most investors"
    elif risk_score >= 40:
        level = "Moderate to High Risk"
        recommendation = "Elevated risk - suitable only for risk-tolerant investors"
    else:
        level = "High Risk"
        recommendation = "High risk profile - not recommended for risk-averse investors"

    return {
        'risk_score': risk_score,
        'max_score': max_score,
        'risk_level': level,
        'recommendation': recommendation,
        'strengths': strengths,
        'issues': issues,
    }
