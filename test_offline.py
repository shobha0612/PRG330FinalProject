# test_offline.py
# Tests the project WITHOUT internet by replacing the API functions with fake data.
# Run:  python test_offline.py
# It uses temporary files, so it never touches your real data/ folder.

import builtins
import contextlib
import io
import math
import os
import tempfile
import warnings
from datetime import datetime, timedelta

import config
import data_fetcher
import fundamentals
import technicals
import portfolio as pf
import risk_manager
import order_engine
import strategy
import backtester
import analytics
import main
import pandas_tools
import numpy_stats
import charts

# ----- use temporary files for the test -----
temp_folder = tempfile.mkdtemp()
config.PORTFOLIO_FILE = os.path.join(temp_folder, "portfolio.json")
config.TRADES_FILE = os.path.join(temp_folder, "trades.csv")
config.ALLOCATION_FILE = os.path.join(temp_folder, "allocation.csv")
config.CACHE_FOLDER = os.path.join(temp_folder, "cache")
config.BACKTEST_EQUITY_FILE = os.path.join(temp_folder, "bt_equity.csv")
config.BACKTEST_TRADES_FILE = os.path.join(temp_folder, "bt_trades.csv")
config.BACKTEST_CHART_FILE = os.path.join(temp_folder, "bt_chart.png")
config.SECONDS_BETWEEN_STOCKS = 0


def make_dates(count):
    """Weekday dates starting 2022-01-03."""
    dates = []
    day = datetime(2022, 1, 3)
    while len(dates) < count:
        if day.weekday() < 5:
            dates.append(day.strftime("%Y-%m-%d"))
        day = day + timedelta(days=1)
    return dates


def fake_history(kind, count=600):
    """Made-up prices: 'up', 'down', 'crash' (last 3 days fall hard), 'round' (up then down), 'market'."""
    closes, opens, highs, lows, volumes = [], [], [], [], []
    price = 100.0
    for day in range(count):
        wave = math.sin(day / 7) * 1.2
        if kind == "up":
            price = price * 1.002 + wave * 0.1
        elif kind == "down":
            price = price * 0.998 + wave * 0.1
        elif kind == "round":
            factor = 1.002 if day < 700 else 0.997
            price = price * factor + wave * 0.1
        elif kind == "market":
            price = price * 1.0004 + wave * 0.05
        else:                                  # crash
            price = price * 1.001 + wave * 0.1
            if day >= count - 3:
                price = price * 0.93
        opens.append(price - 0.3)
        closes.append(price)
        highs.append(price + 1)
        lows.append(price - 1)
        volumes.append(1000000 + (day % 5) * 100000)
    return {"dates": make_dates(count), "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": volumes}


good_tech = {
    "symbol": "GOODTECH", "name": "Good Tech Inc", "sector": "Technology", "industry": "Software",
    "price": 150.0, "pe": 28, "pbv": 9, "peg": 1.6, "ps": 7, "eps": 5.0, "roe": 0.30,
    "gross_margin": 0.70, "operating_margin": 0.30, "profit_margin": 0.25,
    "revenue_growth": 0.18, "earnings_growth": 0.20, "debt_to_equity": 40.0,
    "current_ratio": 1.8, "free_cashflow": -2e9,      # negative FCF because of data-centre capex
    "total_revenue": 50e9, "ebit": 15e9, "total_assets": 100e9, "current_liabilities": 20e9,
    "capex": -25e9, "revenue_history": [50e9, 42e9, 36e9, 30e9],
    "total_debt": 5e9, "total_cash": 10e9, "ebitda": 20e9,
}
round_tech = dict(good_tech)
round_tech["symbol"] = "ROUNDCO"
weak_factory = {
    "symbol": "WEAKCO", "name": "Weak Manufacturing", "sector": "Industrials", "industry": "Machinery",
    "price": 40.0, "pe": 45, "pbv": 6, "eps": 0.5, "roe": 0.03, "operating_margin": 0.03,
    "debt_to_equity": 300.0, "current_ratio": 0.7, "free_cashflow": -1e8,
    "total_revenue": 1e9, "ebit": 3e7, "total_assets": 2e9, "current_liabilities": 8e8,
    "total_debt": 1.5e9, "total_cash": 1e8, "ebitda": 1e8, "revenue_history": [1e9, 1.1e9, 1.2e9],
}

raw_data = {"GOODTECH": good_tech, "ROUNDCO": round_tech, "WEAKCO": weak_factory}
history_data = {
    "GOODTECH": fake_history("up", 1000),
    "ROUNDCO": fake_history("round", 1000),
    "WEAKCO": fake_history("up", 1000),
    "SPY": fake_history("market", 1000),
}

data_fetcher.get_fundamental_data = lambda symbol, use_disk_cache=False: raw_data.get(symbol)
data_fetcher.get_price_history = lambda symbol, use_disk_cache=False: history_data.get(symbol)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed = passed + 1
        print("PASS:", name)
    else:
        failed = failed + 1
        print("FAIL:", name)


def close_to(a, b, tolerance=1e-6):
    return abs(a - b) <= tolerance


# ===========================================================================
print("\n--- Fundamentals ---")
good = fundamentals.analyze_fundamentals(good_tech)
weak = fundamentals.analyze_fundamentals(weak_factory)
check("Tech company with negative FCF but strong ROCE/growth PASSES", good["passed"])
check("Weak industrial is REJECTED", not weak["passed"])
check("ROCE computed (15/(100-20) = 18.75%)", close_to(good["metrics"]["roce"], 0.1875, 0.001))
check("Debt/Equity converted from percent (40 -> 0.4)", close_to(good["metrics"]["debt_to_equity"], 0.4))

# ===========================================================================
print("\n--- Technicals ---")
up = technicals.analyze_technicals(fake_history("up"))
crash = technicals.analyze_technicals(fake_history("crash"))
check("RSI is between 0 and 100", 0 <= up["indicators"]["rsi"] <= 100)
check("Crash is flagged as AGGRESSIVE FALL", any("AGGRESSIVE FALL" in s for s in crash["states"]))
check("Crash never gives a BUY", crash["signal"] != "BUY")
check("Uptrend detected", any("Uptrend" in r for r in up["reasons"]))
bull = technicals.detect_candle_patterns(
    [10, 10, 9.8, 9.5, 9.3, 9.1, 8.8, 8.3],
    [10.1, 10, 9.9, 9.6, 9.4, 9.2, 8.9, 9.4],
    [9.8, 9.7, 9.4, 9.2, 9.0, 8.7, 8.2, 8.2],
    [9.9, 9.8, 9.5, 9.3, 9.1, 8.8, 8.3, 9.3])
check("Bullish engulfing detected", any(name == "Bullish Engulfing" for name, p in bull))

# ===========================================================================
print("\n--- Strategy ---")
check("Weak stock -> REJECT", strategy.evaluate_stock("WEAKCO")["action"] == "REJECT")
check("Owned weak stock -> SELL", strategy.evaluate_stock("WEAKCO", owned=True)["action"] == "SELL")
check("Good stock gets a technical result", strategy.evaluate_stock("GOODTECH")["tech"] is not None)

# ===========================================================================
print("\n--- 5% rule ---")
p = pf.new_portfolio()
prices = {}
check("5% of $100,000 at $150 = 33 shares", risk_manager.max_shares_under_cap(p, "GOODTECH", 150.0, prices) == 33)
qty, msgs, warn = risk_manager.validate_buy(p, "GOODTECH", 100, 150.0, prices, "auto")
check("AUTO order of 100 is cut to 33", qty == 33 and not warn)
qty, msgs, warn = risk_manager.validate_buy(p, "GOODTECH", 100, 150.0, prices, "manual")
check("MANUAL order of 100 allowed but flagged HIGH CONCENTRATION", qty == 100 and warn)
check("Warning text is shown", any("HIGH CONCENTRATION" in m for m in msgs))
config.ALLOW_MANUAL_OVERRIDE = False
qty, msgs, warn = risk_manager.validate_buy(p, "GOODTECH", 100, 150.0, prices, "manual")
check("With override OFF manual order is cut to 33", qty == 33 and not warn)
config.ALLOW_MANUAL_OVERRIDE = True

# ===========================================================================
print("\n--- Trading hours and orders ---")
real_market_open = order_engine.is_market_open
order_engine.is_market_open = lambda: False
status = order_engine.place_order(p, "BUY", "GOODTECH", 10, 150.0, "Technology", "auto")
check("Order while market closed is QUEUED", status == "QUEUED" and len(p["pending_orders"]) == 1)
p["pending_orders"] = []
status = order_engine.place_order(p, "BUY", "GOODTECH", 10, 150.0, "Technology", "auto",
                                  "starter", ignore_hours=True)
check("STARTER order is FILLED even while market is closed", status == "FILLED")
p = pf.new_portfolio()

order_engine.is_market_open = lambda: False
order_engine.place_order(p, "BUY", "GOODTECH", 10, 150.0, "Technology", "auto")
order_engine.is_market_open = lambda: True
order_engine.process_pending_orders(p, {"GOODTECH": 150.0})
check("Queued order filled when market opens", "GOODTECH" in p["holdings"] and p["pending_orders"] == [])
status = order_engine.place_order(p, "BUY", "GOODTECH", 5, 150.0, "Technology", "auto")
check("Order while market open is FILLED", status == "FILLED" and p["holdings"]["GOODTECH"]["shares"] == 15)
status = order_engine.place_order(p, "SELL", "GOODTECH", 15, 160.0, "Technology", "manual")
check("Sell everything removes the holding", status == "FILLED" and "GOODTECH" not in p["holdings"])
check("Cash after profit = 100000 + 15*10", close_to(p["cash"], 100150.0, 0.01))

# ===========================================================================
print("\n--- Files ---")
pf.save_portfolio(p)
check("Portfolio JSON saved and reloaded", pf.load_portfolio()["cash"] == p["cash"])
pf.export_allocation_csv(p, {})
check("Allocation CSV written", os.path.exists(config.ALLOCATION_FILE))
check("Trades CSV written", os.path.exists(config.TRADES_FILE))

history = fake_history("up", 300)
data_fetcher._save_history_file("TEST", history)
loaded = data_fetcher._load_history_file("TEST")
check("Price history survives a disk-cache round trip",
      loaded is not None and loaded["dates"] == history["dates"]
      and all(close_to(a, b, 1e-9) for a, b in zip(loaded["close"], history["close"])))
data_fetcher._save_fundamental_file("TEST", good_tech)
check("Fundamentals survive a disk-cache round trip",
      data_fetcher._load_fundamental_file("TEST")["revenue_history"] == good_tech["revenue_history"])
check("Missing cache file returns None", data_fetcher._load_history_file("NOPE") is None)

# ===========================================================================
print("\n--- Statistics toolbox ---")
check("mean", close_to(analytics.mean([1, 2, 3, 4]), 2.5))
check("median (even count)", close_to(analytics.median([1, 2, 3, 4]), 2.5))
check("sample standard deviation", close_to(analytics.stdev([2, 4, 4, 4, 5, 5, 7, 9]), 2.138089935, 1e-6))
series = [100, 110, 99, 121]
r = analytics.daily_returns(series)
check("daily returns", close_to(r[0], 0.10) and close_to(r[1], -0.10) and close_to(r[2], 22 / 99))
dd, peak_i, trough_i, dd_series = analytics.max_drawdown(series)
check("max drawdown = -10% from 110 to 99", close_to(dd, -0.10) and peak_i == 1 and trough_i == 2)
check("CAGR of 100 -> 121 over 2 years is about 10%",
      close_to(analytics.cagr([100, 121], ["2023-01-01", "2025-01-01"]), 0.10, 0.002))
a = [0.01, -0.02, 0.03, 0.005, -0.01]
b = [2 * x + 0.001 for x in a]
check("correlation of a series with a scaled copy is 1", close_to(analytics.correlation(a, b), 1.0))
beta, alpha = analytics.beta_alpha(a, a)
check("beta of a series against itself is 1 and alpha is 0", close_to(beta, 1.0) and close_to(alpha, 0.0))
check("VaR 95% picks the 5th percentile", analytics.percentile(list(range(1, 101)), 5) == 5)
check("Sharpe of zero-volatility returns is 0 (no crash)", analytics.sharpe_ratio([0.001, 0.001, 0.001]) == 0.0)
check("Longest winning streak", analytics.longest_streak([1, 1, -1, 1, 1, 1, -1], True) == 3)

# ===========================================================================
print("\n--- Backtest ---")
no_look_ahead = backtester.slice_history(history_data["GOODTECH"], 299)
check("slice_history never contains future candles", len(no_look_ahead["close"]) == 300)

results = backtester.run_backtest(["GOODTECH", "ROUNDCO", "WEAKCO"], years=2, start_cash=100000.0,
                                  check_every=5, use_fundamentals=True, use_disk_cache=False)
check("Backtest returns results", results is not None)
n = len(results["dates"])
check("Curves have equal length", len(results["equity"]) == n and len(results["benchmark"]) == n)
check("WEAKCO excluded by fundamentals filter", "WEAKCO" in results["rejected"]
      and "WEAKCO" not in results["stocks_tested"])
check("Day-1 value equals starting cash (no peeking)", close_to(results["equity"][0], 100000.0))
check("Benchmark starts at starting cash", close_to(results["benchmark"][0], 100000.0))
check("Trades happened", len(results["trades"]) > 0)
check("No trade on day 1 (orders fill at the NEXT open)",
      all(t["date"] > results["dates"][0] for t in results["trades"]))
check("Cash never negative", min(results["cash"]) >= 0)
buys = [t for t in results["trades"] if t["side"] == "BUY"]
check("5% cap respected at every purchase",
      len(buys) > 0 and max(t["weight_after"] for t in buys) <= config.MAX_POSITION_PERCENT + 0.5)
sells = [t for t in results["trades"] if t["side"] == "SELL"]
check("Sells record profit and holding period", all(t["hold_days"] >= 0 for t in sells))
unfiltered = backtester.run_backtest(["GOODTECH", "WEAKCO"], years=2, check_every=5,
                                     use_fundamentals=False, use_disk_cache=False)
check("Filter OFF lets the weak stock into the test", "WEAKCO" in unfiltered["stocks_tested"])

# ===========================================================================
print("\n--- Report, files and charts ---")
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    summary = analytics.print_report(results)
text = buffer.getvalue()
check("Report contains descriptive section", "DESCRIPTIVE ANALYSIS" in text)
check("Report contains quantitative section", "QUANTITATIVE ANALYSIS" in text and "Sharpe" in text)
check("Report contains limitations (look-ahead bias)", "Look-ahead bias" in text)
check("Report summary has strategy and benchmark metrics",
      "strategy" in summary and "benchmark" in summary)
with contextlib.redirect_stdout(io.StringIO()):
    analytics.export_csv_files(results)
check("Backtest CSV files written", os.path.exists(config.BACKTEST_EQUITY_FILE)
      and os.path.exists(config.BACKTEST_TRADES_FILE))
with contextlib.redirect_stdout(io.StringIO()):
    chart_ok = analytics.save_charts(results, summary)
check("Chart image written", (not chart_ok) or os.path.getsize(config.BACKTEST_CHART_FILE) > 5000)

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    analytics.print_stock_statistics("GOODTECH", history_data["GOODTECH"], history_data["SPY"], 2)
check("Single-stock statistics report works", "Beta vs benchmark" in buffer.getvalue())

# ===========================================================================
print("\n--- Starter shares (market closed) ---")
order_engine.is_market_open = lambda: False
data_fetcher.get_current_prices = lambda symbols: {s: history_data[s]["close"][-1] for s in symbols if s in history_data}
data_fetcher.get_latest_price = lambda symbol: history_data[symbol]["close"][-1]
main.load_watchlist = lambda: ["GOODTECH", "WEAKCO", "ROUNDCO"]

starter = pf.new_portfolio()
with contextlib.redirect_stdout(io.StringIO()):
    main.build_starter_portfolio(starter)
prices_now = data_fetcher.get_current_prices(list(starter["holdings"].keys()))
weights = [pf.get_allocation_percent(starter, s, prices_now) for s in starter["holdings"]]
check("Auto starter portfolio bought something while the market is closed", len(starter["holdings"]) >= 1)
check("Weak stock was NOT bought", "WEAKCO" not in starter["holdings"])
check("Every starter holding is within the 5% cap", all(w <= config.MAX_POSITION_PERCENT + 0.01 for w in weights))
check("Nothing was left in the pending queue", starter["pending_orders"] == [])

manual = pf.new_portfolio()
answers = ["GOODTECH", "5"]
builtins.input = lambda prompt="": answers.pop(0)
with contextlib.redirect_stdout(io.StringIO()):
    main.manual_buy(manual, starter=True)
check("Manual starter shares filled while market is closed",
      "GOODTECH" in manual["holdings"] and manual["holdings"]["GOODTECH"]["shares"] == 5)

# ===========================================================================
print("\n--- Trimming winners back to the 5% cap ---")
big = pf.new_portfolio()
big["cash"] = 90000.0
big["holdings"] = {"GOODTECH": {"shares": 100, "avg_price": 50.0, "sector": "Technology"}}
trim_prices = {"GOODTECH": 100.0}      # position = $10,000 of $100,000 total = 10%
excess = risk_manager.shares_to_trim(big, "GOODTECH", 100.0, trim_prices)
check("10% position is trimmed (50 shares -> back to 5%)", excess == 50)
big["holdings"]["GOODTECH"]["shares"] = 55           # $5,500 / $95,500 -> about 5.8%, inside tolerance
check("5.8% position is inside the tolerance: no trim",
      risk_manager.shares_to_trim(big, "GOODTECH", 100.0, trim_prices) == 0)

trim_trades = [t for t in results["trades"] if t["side"] == "TRIM"]
check("Backtest trimmed the big winner at least once", len(trim_trades) > 0)
check("Weight never ran far past the cap in the backtest",
      max(results["max_weight"]) <= config.MAX_POSITION_PERCENT + config.REBALANCE_TOLERANCE_PERCENT + 2.0)
check("Trim trades are partial sells (position still open afterwards)",
      "GOODTECH" in results["final_portfolio"]["holdings"])

# live auto-trader trims too
live = pf.new_portfolio()
live["cash"] = 90000.0
live["holdings"] = {"GOODTECH": {"shares": 100, "avg_price": 50.0, "sector": "Technology"}}
order_engine.is_market_open = lambda: True
real_evaluate = strategy.evaluate_stock
strategy.evaluate_stock = lambda symbol, owned=False: {
    "symbol": symbol, "price": 100.0, "sector": "Technology", "action": "HOLD", "why": "test"}
data_fetcher.get_current_prices = lambda symbols: {"GOODTECH": 100.0}
main.load_watchlist = lambda: ["GOODTECH"]
with contextlib.redirect_stdout(io.StringIO()):
    main.auto_scan(live)
check("Live auto-trader trims an over-weight stock back to the cap",
      live["holdings"]["GOODTECH"]["shares"] == 50)
strategy.evaluate_stock = real_evaluate

order_engine.is_market_open = real_market_open

# ===========================================================================
print("\n--- NumPy / pandas / matplotlib layer ---")
config.CHART_FOLDER = os.path.join(temp_folder, "charts")
config.TABLE_FOLDER = os.path.join(temp_folder, "tables")
library_table = pandas_tools.add_indicators(pandas_tools.history_to_dataframe(history))
indicator_rows = numpy_stats.verify_indicators(history)
check("Pandas indicators agree with the hand-written indicators",
      max(row["difference"] for row in indicator_rows) < 0.001)
metric_rows = numpy_stats.verify_metrics(history["close"], history["dates"])
check("NumPy metrics agree with analytics metrics",
      max(row["difference"] for row in metric_rows) < 0.001)
simulation_a = numpy_stats.monte_carlo(history["close"], 30, 20, seed=42)
simulation_b = numpy_stats.monte_carlo(history["close"], 30, 20, seed=42)
check("Monte Carlo is repeatable with a fixed seed",
      (simulation_a["end_values"] == simulation_b["end_values"]).all())
close_table = pandas_tools.history_to_dataframe(history)[["close"]].rename(
    columns={"close": "GOODTECH"})
close_table["ROUNDCO"] = close_table["GOODTECH"] * 1.02
portfolio_result = numpy_stats.random_portfolios(close_table, 30, seed=7)
weights = portfolio_result["portfolios"][["GOODTECH", "ROUNDCO"]].sum(axis=1)
check("Random portfolio weights sum to 1", all(abs(value - 1) < 1e-10 for value in weights))
never_falling = dict(history)
never_falling["close"] = list(range(100, 100 + len(history["close"])))
with warnings.catch_warnings(record=True) as warning_list:
    warnings.simplefilter("always")
    never_falling_table = pandas_tools.add_indicators(
        pandas_tools.history_to_dataframe(never_falling))
check("Never-falling RSI is 100 without a warning",
      never_falling_table["rsi14"].iloc[-1] == 100 and len(warning_list) == 0)
low_volume = dict(history)
low_volume["volume"] = [1000] * len(history["volume"])
chart_paths = [
    charts.candlestick_dashboard("LOWVOL", low_volume),
    charts.equity_dashboard(results),
    charts.monthly_heatmap(results),
    charts.return_distribution(results["equity"]),
    charts.trade_analysis(results),
    charts.plan_outcomes_chart([]),
    charts.allocation_charts(results["final_portfolio"], results["final_prices"]),
    charts.monte_carlo_chart(simulation_a),
    charts.frontier_chart(portfolio_result, close_table),
    charts.correlation_heatmap(pandas_tools.correlation_table(close_table)),
    charts.normalised_prices_chart(close_table, pandas_tools.watchlist_statistics(close_table)),
    charts.fundamentals_scorecard(good_tech, good),
    charts.fundamentals_peer_chart(pandas_tools.fundamentals_table(["GOODTECH"], False)),
]
check("Every chart writes a non-trivial PNG",
      all(os.path.exists(path) and os.path.getsize(path) > 3000 for path in chart_paths))
long_correlation = pandas_tools.correlation_table(close_table.rename(
    columns={"GOODTECH": "A_VERY_LONG_TICKER_NAME", "ROUNDCO": "ANOTHER_LONG_TICKER_NAME"}))
long_chart = charts.correlation_heatmap(long_correlation)
check("Long ticker correlation chart is drawn", os.path.getsize(long_chart) > 3000)
gallery = charts.write_gallery(chart_paths, "Offline chart gallery")
check("Chart gallery file exists", os.path.exists(gallery))

print("\nResult:", passed, "passed,", failed, "failed")
