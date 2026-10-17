# NumPy statistics, simulations and checks against the hand-written toolbox.
# Concepts used: arrays, vectorised calculations, random seeds, bootstrap samples.

import math

import numpy as np
import pandas as pd

import analytics
import config
import pandas_tools
import technicals


def numpy_returns(values):
    """Returns percentage changes between consecutive values as a NumPy array."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return np.array([])
    return values[1:] / values[:-1] - 1


def _numpy_cagr(values, dates):
    """Calculates CAGR with the same calendar-day convention as analytics.py."""
    if len(values) == 0 or values[0] <= 0 or values[-1] <= 0:
        return 0.0
    first = pd.Timestamp(dates[0])
    last = pd.Timestamp(dates[-1])
    years = (last - first).days / 365.25
    if years <= 0:
        return 0.0
    return (values[-1] / values[0]) ** (1 / years) - 1


def numpy_metrics(values, dates):
    """Calculates common portfolio metrics using NumPy and pandas."""
    values = np.asarray(values, dtype=float)
    returns = numpy_returns(values)
    if len(values) == 0:
        return {}
    running_peak = np.maximum.accumulate(values)
    drawdowns = values / running_peak - 1
    daily_free = config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR
    std = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
    downside = np.minimum(0, returns - daily_free)
    downside_std = np.sqrt(np.mean(downside ** 2)) if len(returns) else 0.0
    sharpe = (np.mean(returns) - daily_free) / std * math.sqrt(
        config.TRADING_DAYS_PER_YEAR) if std else 0.0
    sortino = (np.mean(returns) - daily_free) / downside_std * math.sqrt(
        config.TRADING_DAYS_PER_YEAR) if downside_std else 0.0
    return {
        "total_return": values[-1] / values[0] - 1,
        "cagr": _numpy_cagr(values, dates),
        "volatility": std * math.sqrt(config.TRADING_DAYS_PER_YEAR),
        "sharpe": sharpe, "sortino": sortino, "max_dd": np.min(drawdowns),
        "var95": float(np.sort(returns)[int(0.05 * (len(returns) - 1))])
        if len(returns) else 0.0,
        "drawdown_series": drawdowns,
    }


def numpy_beta_alpha(values, bench_values):
    """Calculates beta and annual alpha for two value series."""
    returns = numpy_returns(values)
    bench_returns = numpy_returns(bench_values)
    if len(returns) < 2 or len(bench_returns) < 2:
        return 0.0, 0.0
    variance = np.var(bench_returns, ddof=1)
    if variance == 0:
        return 0.0, 0.0
    beta = np.cov(returns, bench_returns, ddof=1)[0, 1] / variance
    daily_free = config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR
    alpha = ((np.mean(returns) - daily_free) -
             beta * (np.mean(bench_returns) - daily_free)) * config.TRADING_DAYS_PER_YEAR
    return beta, alpha


def verify_metrics(values, dates):
    """Compares hand-written metrics with their NumPy equivalents."""
    ours = analytics.compute_metrics(list(values), list(dates))
    library = numpy_metrics(values, dates)
    names = ["total_return", "cagr", "volatility", "sharpe", "sortino", "max_dd", "var95"]
    rows = []
    for name in names:
        rows.append({"name": name, "our_value": ours[name],
                     "library_value": float(library[name]),
                     "difference": abs(ours[name] - float(library[name]))})
    return rows


def verify_indicators(history):
    """Compares the latest plain-Python indicators with the pandas indicators."""
    plain = technicals.analyze_technicals(history)["indicators"]
    table = pandas_tools.add_indicators(pandas_tools.history_to_dataframe(history))
    latest = table.iloc[-1]
    pairs = [("sma20", "sma20"), ("sma50", "sma50"), ("sma200", "sma200"),
             ("rsi", "rsi14"), ("macd", "macd"), ("macd_signal", "signal")]
    rows = []
    for ours_name, library_name in pairs:
        ours = plain.get(ours_name)
        library = latest[library_name]
        if pd.isna(library):
            library = None
        difference = abs(ours - library) if ours is not None and library is not None else 0.0
        rows.append({"name": ours_name, "our_value": ours, "library_value": library,
                     "difference": difference})
    return rows


def print_verification(rows, title):
    """Prints verification rows and marks small differences as OK."""
    print("\n" + title)
    print("{:<18}{:>16}{:>16}{:>16}  {}".format(
        "Name", "Our loop", "Library", "Difference", "Result"))
    for row in rows:
        result = "OK" if row["difference"] < 1e-5 else "CHECK"
        print("{:<18}{:>16.6f}{:>16.6f}{:>16.6f}  {}".format(
            row["name"], row["our_value"] or 0, row["library_value"] or 0,
            row["difference"], result))


def monte_carlo(values, days, paths, seed=42):
    """Simulates future paths by bootstrapping historical daily returns."""
    returns = numpy_returns(values)
    generator = np.random.default_rng(seed)
    if len(returns) == 0:
        returns = np.array([0.0])
    sampled = generator.choice(returns, size=(paths, days), replace=True)
    paths_values = np.asarray(values[-1]) * np.cumprod(1 + sampled, axis=1)
    end_values = paths_values[:, -1]
    return {
        "paths": paths_values, "end_values": end_values, "start_value": float(values[-1]),
        "days": days, "percentiles": {str(p): float(np.percentile(end_values, p))
                                      for p in [5, 25, 50, 75, 95]},
        "chance_loss": float(np.mean(end_values < values[-1])),
        "chance_gain_10": float(np.mean(end_values >= values[-1] * 1.10)),
        "seed": seed,
    }


def print_monte_carlo(sim):
    """Prints Monte Carlo percentiles and outcome probabilities."""
    print("\nMONTE CARLO SIMULATION")
    for percentile in [5, 25, 50, 75, 95]:
        print(str(percentile) + "th percentile:", round(sim["percentiles"][str(percentile)], 2))
    print("Chance of loss:", round(sim["chance_loss"] * 100, 1), "%")
    print("Chance of gaining over 10%:", round(sim["chance_gain_10"] * 100, 1), "%")


def random_portfolios(closes, count, seed=7):
    """Generates random portfolios and returns the best, safest and equal-weight choices."""
    prices = closes.dropna()
    returns = prices.pct_change().dropna()
    symbols = list(prices.columns)
    generator = np.random.default_rng(seed)
    if len(symbols) == 0:
        return {"portfolios": pd.DataFrame(), "best_sharpe": None,
                "lowest_risk": None, "equal_weight": None}
    weights = generator.dirichlet(np.ones(len(symbols)), size=count)
    annual_returns = returns.mean().to_numpy() @ weights.T * config.TRADING_DAYS_PER_YEAR
    annual_volatility = np.sqrt(np.einsum("ij,jk,ik->i", weights,
                                          returns.cov().to_numpy() * config.TRADING_DAYS_PER_YEAR,
                                          weights))
    annual_sharpe = (annual_returns - config.RISK_FREE_RATE) / np.where(
        annual_volatility == 0, 1, annual_volatility)
    frame = pd.DataFrame(weights, columns=symbols)
    frame["return"] = annual_returns
    frame["volatility"] = annual_volatility
    frame["sharpe"] = annual_sharpe
    equal = np.ones(len(symbols)) / len(symbols)
    equal_row = {"weights": dict(zip(symbols, equal)),
                 "return": float(returns.mean().to_numpy() @ equal * config.TRADING_DAYS_PER_YEAR),
                 "volatility": float(np.sqrt(equal @ (returns.cov().to_numpy() *
                                                       config.TRADING_DAYS_PER_YEAR) @ equal))}
    equal_row["sharpe"] = (equal_row["return"] - config.RISK_FREE_RATE) / equal_row["volatility"] \
        if equal_row["volatility"] else 0.0
    return {
        "portfolios": frame, "symbols": symbols,
        "best_sharpe": frame.loc[frame["sharpe"].idxmax()].to_dict(),
        "lowest_risk": frame.loc[frame["volatility"].idxmin()].to_dict(),
        "equal_weight": equal_row,
    }


def print_random_portfolios(result):
    """Prints the three representative portfolio choices."""
    for name in ["best_sharpe", "lowest_risk", "equal_weight"]:
        row = result.get(name)
        if row is not None:
            print(name + ":", row)
