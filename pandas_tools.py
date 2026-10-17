# Library tables and indicators built with pandas.
# Concepts used: DataFrame tables, rolling windows, exponential averages, groupby.

import os

import numpy as np
import pandas as pd

import analytics
import config
import data_fetcher
import fundamentals
import technicals


def history_to_dataframe(history):
    """Converts a price-history dictionary into a dated pandas table."""
    table = pd.DataFrame({
        "open": history["open"], "high": history["high"],
        "low": history["low"], "close": history["close"], "volume": history["volume"]
    }, index=pd.to_datetime(history["dates"]))
    table.index.name = "date"
    return table


def results_to_dataframe(results):
    """Converts backtest curves into a dated pandas table."""
    columns = ["equity", "benchmark", "cash", "invested_pct", "positions", "max_weight"]
    data = {}
    for name in columns:
        if name in results:
            data[name] = results[name]
    return pd.DataFrame(data, index=pd.to_datetime(results["dates"]))


def trades_to_dataframe(trades):
    """Converts trade dictionaries into a pandas table."""
    if not trades:
        return pd.DataFrame()
    return pd.DataFrame(trades)


def add_indicators(table):
    """Adds moving averages, bands, RSI, MACD and ATR to a price table."""
    result = table.copy()
    close = result["close"]
    high = result["high"] if "high" in result else close
    low = result["low"] if "low" in result else close
    result["sma20"] = close.rolling(20).mean()
    result["sma50"] = close.rolling(50).mean()
    result["sma200"] = close.rolling(200).mean()
    middle = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    result["bollinger_upper"] = middle + 2 * std
    result["bollinger_lower"] = middle - 2 * std

    change = close.diff()
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)
    average_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    average_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    result["rsi14"] = 100 - (100 / (1 + relative_strength))
    result.loc[(average_loss == 0) & (average_gain > 0), "rsi14"] = 100.0
    result.loc[(average_loss == 0) & (average_gain == 0), "rsi14"] = 50.0

    result["macd"] = close.ewm(span=12, adjust=False).mean() - close.ewm(
        span=26, adjust=False).mean()
    result["signal"] = result["macd"].ewm(span=9, adjust=False).mean()
    result["histogram"] = result["macd"] - result["signal"]
    previous_close = close.shift(1)
    true_range = pd.concat([
        high - low, (high - previous_close).abs(), (low - previous_close).abs()
    ], axis=1).max(axis=1)
    result["atr14"] = true_range.rolling(14).mean()
    return result


def describe_returns_table(table):
    """Returns pandas descriptive statistics for the numeric price or return columns."""
    return table.describe()


def monthly_returns_table(equity_series):
    """Returns a year by month table of compounded monthly returns."""
    series = pd.Series(equity_series).copy()
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.to_datetime(series.index)
    monthly = series.resample("ME").last().pct_change()
    result = monthly.to_frame("return")
    result["year"] = result.index.year
    result["month"] = result.index.month
    return result.pivot(index="year", columns="month", values="return").reindex(columns=range(1, 13))


def drawdown_series(equity_series):
    """Returns the percentage fall from each running equity peak."""
    series = pd.Series(equity_series)
    return series / series.cummax() - 1


def rolling_sharpe(returns, window=63):
    """Returns an annualised rolling Sharpe ratio for a return series."""
    series = pd.Series(returns)
    daily_free = config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR
    return (series.rolling(window).mean() - daily_free) / series.rolling(window).std(
        ddof=1) * np.sqrt(config.TRADING_DAYS_PER_YEAR)


def trade_tables(trades_table):
    """Groups realised trade profit by symbol and by sector."""
    if trades_table.empty:
        empty = pd.DataFrame(columns=["pnl"])
        return empty, empty.copy()
    closed = trades_table[trades_table["side"].isin(["SELL", "TRIM"])].copy()
    by_symbol = closed.groupby("symbol", as_index=True)["pnl"].sum().to_frame("pnl")
    by_sector = closed.groupby("sector", as_index=True)["pnl"].sum().to_frame("pnl")
    return by_symbol.sort_values("pnl", ascending=False), by_sector.sort_values("pnl", ascending=False)


def load_close_table(symbols, years, use_disk_cache):
    """Loads close prices for symbols into one date-indexed DataFrame."""
    series = {}
    for symbol in symbols:
        history = data_fetcher.get_price_history(symbol, use_disk_cache)
        if history is not None:
            series[symbol] = history_to_dataframe(history)["close"]
    if not series:
        return pd.DataFrame()
    table = pd.concat(series, axis=1).sort_index()
    wanted = int(years * config.TRADING_DAYS_PER_YEAR) + 1
    return table.tail(wanted)


def watchlist_statistics(closes):
    """Calculates and sorts risk and return statistics for each close-price column."""
    rows = []
    for symbol in closes.columns:
        series = closes[symbol].dropna()
        if len(series) < 2:
            continue
        values = series.tolist()
        dates = [day.strftime("%Y-%m-%d") for day in series.index]
        returns = analytics.daily_returns(values)
        metrics = analytics.compute_metrics(values, dates)
        indicators = add_indicators(pd.DataFrame({"close": series})).iloc[-1]
        rows.append({
            "symbol": symbol, "total_return": metrics["total_return"], "cagr": metrics["cagr"],
            "volatility": metrics["volatility"], "sharpe": metrics["sharpe"],
            "max_drawdown": metrics["max_dd"], "rsi_now": indicators["rsi14"],
            "vs_sma200_pct": (values[-1] / indicators["sma200"] - 1) * 100
            if pd.notna(indicators["sma200"]) and indicators["sma200"] != 0 else np.nan,
        })
    return pd.DataFrame(rows).sort_values("sharpe", ascending=False).reset_index(drop=True)


def correlation_table(closes):
    """Returns the correlation matrix of close-price daily returns."""
    return closes.pct_change().corr()


def portfolio_to_dataframe(portfolio, prices):
    """Builds a holdings table and returns it with total portfolio value."""
    total = portfolio["cash"]
    rows = []
    for symbol, holding in portfolio["holdings"].items():
        price = prices.get(symbol, holding["avg_price"])
        value = holding["shares"] * price
        total += value
        rows.append({"symbol": symbol, "sector": holding.get("sector", "Unknown"),
                     "shares": holding["shares"], "avg_price": holding["avg_price"],
                     "price": price, "value": value})
    rows.append({"symbol": "CASH", "sector": "Cash", "shares": 0, "avg_price": 0,
                 "price": 1, "value": portfolio["cash"]})
    table = pd.DataFrame(rows)
    table["weight_%"] = table["value"] / total * 100 if total else 0
    table["high_concentration"] = table["weight_%"] > config.MAX_POSITION_PERCENT
    return table, total


def fundamentals_table(symbols, use_disk_cache):
    """Loads and analyses fundamentals, returning one row per available company."""
    rows = []
    for symbol in symbols:
        raw = data_fetcher.get_fundamental_data(symbol, use_disk_cache)
        if raw is None:
            continue
        verdict = fundamentals.analyze_fundamentals(raw)
        row = {"symbol": symbol, "name": raw.get("name"), "sector": verdict["sector"],
               "passed": verdict["passed"], "score_percent": verdict["score_percent"],
               "reason": verdict["reason"]}
        row.update(verdict["metrics"])
        rows.append(row)
    return pd.DataFrame(rows)


def save_table(table, path):
    """Creates the destination folder and saves a DataFrame as CSV."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    table.to_csv(path)
    return path


def print_pandas_report(results):
    """Prints and saves the main pandas tables for a backtest."""
    curves = results_to_dataframe(results)
    trades = trades_to_dataframe(results.get("trades", []))
    tables = {"backtest_curves": curves, "trades": trades}
    for name, table in tables.items():
        print("\n--- pandas:", name, "---")
        print(table)
        save_table(table, os.path.join(config.TABLE_FOLDER, name + ".csv"))
    return tables
