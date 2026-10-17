# analytics.py
# MODULE 10 - Descriptive and quantitative analysis of results.
# Concepts used: lists, for loops, math, sorting, dictionaries, string formatting, csv
#
#   DESCRIPTIVE analysis = "What happened?"
#       averages, spread, best/worst days, how often we won, streaks, shape of returns.
#   QUANTITATIVE analysis = "How good was it, adjusted for risk?"
#       CAGR, volatility, Sharpe, Sortino, drawdown, beta, alpha, VaR, profit factor.
#
# All statistics are written by hand with simple loops, so every formula is visible.

import csv
import math
import os
from datetime import datetime

import config


# ===========================================================================
# PART 1 - BASIC STATISTICS TOOLBOX
# ===========================================================================
def mean(values):
    if len(values) == 0:
        return 0.0
    return sum(values) / len(values)


def median(values):
    if len(values) == 0:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def stdev(values):
    """Sample standard deviation (divide by n-1)."""
    n = len(values)
    if n < 2:
        return 0.0
    m = mean(values)
    total = 0.0
    for v in values:
        total = total + (v - m) ** 2
    return (total / (n - 1)) ** 0.5


def percentile(values, percent):
    """Simple percentile: sort the numbers and pick the one at that position."""
    if len(values) == 0:
        return 0.0
    ordered = sorted(values)
    position = int(percent / 100 * (len(ordered) - 1))
    return ordered[position]


def skewness(values):
    """Positive = occasional big gains, negative = occasional big losses."""
    n = len(values)
    m = mean(values)
    s = (sum((v - m) ** 2 for v in values) / n) ** 0.5 if n > 0 else 0
    if s == 0:
        return 0.0
    total = 0.0
    for v in values:
        total = total + ((v - m) / s) ** 3
    return total / n


def excess_kurtosis(values):
    """Above 0 = 'fat tails': extreme days happen more often than a bell curve predicts."""
    n = len(values)
    m = mean(values)
    s = (sum((v - m) ** 2 for v in values) / n) ** 0.5 if n > 0 else 0
    if s == 0:
        return 0.0
    total = 0.0
    for v in values:
        total = total + ((v - m) / s) ** 4
    return total / n - 3


def covariance(a, b):
    n = len(a)
    if n < 2:
        return 0.0
    ma = mean(a)
    mb = mean(b)
    total = 0.0
    for i in range(n):
        total = total + (a[i] - ma) * (b[i] - mb)
    return total / (n - 1)


def correlation(a, b):
    sa = stdev(a)
    sb = stdev(b)
    if sa == 0 or sb == 0:
        return 0.0
    return covariance(a, b) / (sa * sb)


def daily_returns(values):
    """[100, 110, 99] -> [0.10, -0.10]"""
    returns = []
    for i in range(1, len(values)):
        returns.append(values[i] / values[i - 1] - 1)
    return returns


def longest_streak(returns, positive):
    """Longest run of up days (positive=True) or down days (positive=False)."""
    best = 0
    current = 0
    for r in returns:
        if (positive and r > 0) or ((not positive) and r < 0):
            current = current + 1
            if current > best:
                best = current
        else:
            current = 0
    return best


# ===========================================================================
# PART 2 - RISK / RETURN METRICS (QUANTITATIVE)
# ===========================================================================
def max_drawdown(values):
    """
    Worst fall from a previous peak. Returns (drawdown, peak_index, trough_index, series)
    drawdown is negative, e.g. -0.18 means -18%.
    """
    peak = values[0]
    peak_index = 0
    worst = 0.0
    worst_peak = 0
    worst_trough = 0
    series = []
    for i in range(len(values)):
        if values[i] > peak:
            peak = values[i]
            peak_index = i
        drawdown = values[i] / peak - 1
        series.append(drawdown)
        if drawdown < worst:
            worst = drawdown
            worst_peak = peak_index
            worst_trough = i
    return worst, worst_peak, worst_trough, series


def cagr(values, dates):
    """Compound Annual Growth Rate: the steady yearly growth that gives the same result."""
    first = datetime.strptime(dates[0], "%Y-%m-%d")
    last = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (last - first).days / 365.25
    if years <= 0 or values[0] <= 0 or values[-1] <= 0:
        return 0.0
    return (values[-1] / values[0]) ** (1 / years) - 1


def sharpe_ratio(returns):
    """Extra return over the risk-free rate, per unit of total risk (annualised)."""
    daily_free = config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR
    spread = stdev(returns)
    if spread == 0:
        return 0.0
    return (mean(returns) - daily_free) / spread * math.sqrt(config.TRADING_DAYS_PER_YEAR)


def sortino_ratio(returns):
    """Like Sharpe, but only DOWNSIDE moves count as risk."""
    daily_free = config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR
    total = 0.0
    for r in returns:
        shortfall = min(0.0, r - daily_free)
        total = total + shortfall ** 2
    if len(returns) == 0 or total == 0:
        return 0.0
    downside = (total / len(returns)) ** 0.5
    return (mean(returns) - daily_free) / downside * math.sqrt(config.TRADING_DAYS_PER_YEAR)


def beta_alpha(returns, bench_returns):
    """
    beta  = how strongly we move with the market (1.0 = same as the market)
    alpha = yearly return NOT explained by the market (skill, or luck)
    """
    variance = stdev(bench_returns) ** 2
    if variance == 0:
        return 0.0, 0.0
    beta = covariance(returns, bench_returns) / variance
    daily_free = config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR
    daily_alpha = (mean(returns) - daily_free) - beta * (mean(bench_returns) - daily_free)
    return beta, daily_alpha * config.TRADING_DAYS_PER_YEAR


def compute_metrics(values, dates, bench_values=None):
    """All quantitative metrics for ONE value series (portfolio, benchmark or a stock)."""
    returns = daily_returns(values)
    drawdown, peak_i, trough_i, series = max_drawdown(values)
    years_cagr = cagr(values, dates)

    metrics = {
        "total_return": values[-1] / values[0] - 1,
        "cagr": years_cagr,
        "volatility": stdev(returns) * math.sqrt(config.TRADING_DAYS_PER_YEAR),
        "sharpe": sharpe_ratio(returns),
        "sortino": sortino_ratio(returns),
        "max_dd": drawdown,
        "dd_peak_date": dates[peak_i],
        "dd_trough_date": dates[trough_i],
        "drawdown_series": series,
        "calmar": 0.0,
        "var95": percentile(returns, 5),       # on the worst 5% of days we lose at least this much
        "beta": None,
        "alpha": None,
        "corr": None,
        "final_value": values[-1],
    }
    if drawdown < 0:
        metrics["calmar"] = years_cagr / abs(drawdown)

    if bench_values is not None:
        bench_returns = daily_returns(bench_values)
        beta, alpha = beta_alpha(returns, bench_returns)
        metrics["beta"] = beta
        metrics["alpha"] = alpha
        metrics["corr"] = correlation(returns, bench_returns)
    return metrics


# ===========================================================================
# PART 3 - DESCRIPTIVE STATISTICS
# ===========================================================================
def describe_returns(values, dates):
    """Descriptive statistics of daily returns (and monthly returns)."""
    returns = daily_returns(values)
    return_dates = dates[1:]                     # return i happened on dates[i + 1]

    best_i = returns.index(max(returns))
    worst_i = returns.index(min(returns))
    up_days = 0
    for r in returns:
        if r > 0:
            up_days = up_days + 1

    # Monthly returns: last value of each month versus the last value of the month before
    month_end = {}
    month_order = []
    for i in range(len(dates)):
        month = dates[i][:7]                     # "2025-03"
        if month not in month_end:
            month_order.append(month)
        month_end[month] = values[i]
    monthly = []
    previous = values[0]
    for month in month_order:
        monthly.append((month, month_end[month] / previous - 1))
        previous = month_end[month]
    monthly_values = [m[1] for m in monthly]
    best_month = max(monthly, key=lambda item: item[1])
    worst_month = min(monthly, key=lambda item: item[1])
    up_months = 0
    for r in monthly_values:
        if r > 0:
            up_months = up_months + 1

    return {
        "days": len(returns),
        "mean": mean(returns),
        "median": median(returns),
        "stdev": stdev(returns),
        "min": min(returns), "min_date": return_dates[worst_i],
        "max": max(returns), "max_date": return_dates[best_i],
        "skew": skewness(returns),
        "kurtosis": excess_kurtosis(returns),
        "pct_up_days": up_days / len(returns) * 100,
        "longest_up": longest_streak(returns, True),
        "longest_down": longest_streak(returns, False),
        "months": len(monthly),
        "monthly_mean": mean(monthly_values),
        "best_month": best_month, "worst_month": worst_month,
        "pct_up_months": up_months / len(monthly) * 100 if len(monthly) > 0 else 0,
    }


def describe_trades(trades):
    """Statistics of finished (sold) trades."""
    sells = []
    trims = []
    fees = 0.0
    for t in trades:
        fees = fees + t["fee"]
        if t["side"] == "SELL":
            sells.append(t)
        elif t["side"] == "TRIM":
            trims.append(t)

    stats = {"total_orders": len(trades), "closed": len(sells), "fees": fees,
             "trims": len(trims), "trim_pnl": sum(t["pnl"] for t in trims),
             "wins": 0, "losses": 0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
             "profit_factor": None, "expectancy": 0.0, "avg_hold_days": 0.0,
             "best": None, "worst": None, "by_symbol": {}}
    if len(sells) == 0:
        return stats

    win_amounts = []
    loss_amounts = []
    hold_days = []
    for t in sells:
        hold_days.append(t["hold_days"])
        if t["pnl"] > 0:
            win_amounts.append(t["pnl"])
        else:
            loss_amounts.append(t["pnl"])
        symbol = t["symbol"]
        if symbol not in stats["by_symbol"]:
            stats["by_symbol"][symbol] = {"pnl": 0.0, "trades": 0, "wins": 0}
        stats["by_symbol"][symbol]["pnl"] += t["pnl"]
        stats["by_symbol"][symbol]["trades"] += 1
        if t["pnl"] > 0:
            stats["by_symbol"][symbol]["wins"] += 1

    stats["wins"] = len(win_amounts)
    stats["losses"] = len(loss_amounts)
    stats["win_rate"] = len(win_amounts) / len(sells) * 100
    stats["avg_win"] = mean(win_amounts)
    stats["avg_loss"] = mean(loss_amounts)
    if sum(loss_amounts) != 0:
        stats["profit_factor"] = sum(win_amounts) / abs(sum(loss_amounts))
    stats["expectancy"] = mean([t["pnl"] for t in sells])
    stats["avg_hold_days"] = mean(hold_days)
    stats["best"] = max(sells, key=lambda t: t["pnl"])
    stats["worst"] = min(sells, key=lambda t: t["pnl"])
    return stats


# ===========================================================================
# PART 4 - PRINTING
# ===========================================================================
def pct(x):
    if x is None:
        return "-"
    return format(x * 100, "+.2f") + "%"


def pct_plain(x):
    if x is None:
        return "-"
    return format(x * 100, ".2f") + "%"


def num(x):
    if x is None:
        return "-"
    return format(x, ".2f")


def money(x):
    return "$" + format(x, ",.0f")


def print_descriptive(d, title):
    print("\n" + title)
    print("-" * 60)
    print("Trading days analysed        :", d["days"])
    print("Mean daily return            :", pct(d["mean"]))
    print("Median daily return          :", pct(d["median"]))
    print("Std deviation (daily)        :", pct_plain(d["stdev"]))
    print("Best day                     :", pct(d["max"]), "on", d["max_date"])
    print("Worst day                    :", pct(d["min"]), "on", d["min_date"])
    print("Up days                      :", round(d["pct_up_days"], 1), "%")
    print("Longest winning / losing run :", d["longest_up"], "days /", d["longest_down"], "days")
    print("Skewness                     :", num(d["skew"]),
          "(negative = occasional big losses)" if d["skew"] < 0 else "(positive = occasional big gains)")
    print("Excess kurtosis              :", num(d["kurtosis"]),
          "(>0 = fat tails, extreme days are common)" if d["kurtosis"] > 0 else "(thin tails)")
    print("Months analysed              :", d["months"], "| up months:", round(d["pct_up_months"], 1), "%")
    print("Average month                :", pct(d["monthly_mean"]))
    print("Best month                   :", d["best_month"][0], pct(d["best_month"][1]))
    print("Worst month                  :", d["worst_month"][0], pct(d["worst_month"][1]))


def print_metrics_table(columns):
    """columns = [(name, metrics_dict), ...] -> one table with the metrics side by side."""
    rows = [
        ("Final value", "final_value", "money"),
        ("Total return", "total_return", "pct"),
        ("CAGR (yearly growth)", "cagr", "pct"),
        ("Volatility (annual)", "volatility", "plain"),
        ("Sharpe ratio", "sharpe", "num"),
        ("Sortino ratio", "sortino", "num"),
        ("Max drawdown", "max_dd", "pct"),
        ("Calmar ratio", "calmar", "num"),
        ("Daily VaR 95%", "var95", "pct"),
        ("Beta vs benchmark", "beta", "num"),
        ("Alpha (yearly)", "alpha", "pct"),
        ("Correlation vs benchmark", "corr", "num"),
    ]
    line = "{:<26}".format("Metric")
    for name, metrics in columns:
        line = line + "{:>16}".format(name)
    print(line)
    print("-" * len(line))
    for label, key, kind in rows:
        line = "{:<26}".format(label)
        for name, metrics in columns:
            value = metrics[key]
            if kind == "pct":
                text = pct(value)
            elif kind == "plain":
                text = pct_plain(value)
            elif kind == "money":
                text = money(value)
            else:
                text = num(value)
            line = line + "{:>16}".format(text)
        print(line)


def print_trade_stats(t):
    print("\nTRADE STATISTICS")
    print("-" * 60)
    print("Orders placed (buys + sells) :", t["total_orders"])
    print("Finished trades              :", t["closed"])
    print("Rebalancing trims            :", t["trims"], "(winners sold back to the cap, realised",
          money(t["trim_pnl"]) + ")")
    print("Transaction costs paid       :", money(t["fees"]))
    if t["closed"] == 0:
        print("No trade has been closed yet, so win rate and profit factor are not available.")
        return
    print("Win rate                     :", round(t["win_rate"], 1), "% (" + str(t["wins"]) + " wins,",
          t["losses"], "losses)")
    print("Average win / average loss   :", money(t["avg_win"]), "/", money(t["avg_loss"]))
    if t["profit_factor"] is None:
        print("Profit factor                : no losing trades")
    else:
        print("Profit factor                :", num(t["profit_factor"]), "(total wins / total losses)")
    print("Expectancy per trade         :", money(t["expectancy"]))
    print("Average holding period       :", round(t["avg_hold_days"]), "days")
    print("Best trade                   :", t["best"]["symbol"], money(t["best"]["pnl"]),
          "(" + format(t["best"]["return_pct"], "+.1f") + "%)")
    print("Worst trade                  :", t["worst"]["symbol"], money(t["worst"]["pnl"]),
          "(" + format(t["worst"]["return_pct"], "+.1f") + "%)")

    print("\nProfit / loss by stock (finished trades):")
    ranking = sorted(t["by_symbol"].items(), key=lambda item: item[1]["pnl"], reverse=True)
    for symbol, info in ranking:
        print("  {:<7}{:>12}   {} trade(s), {} win(s)".format(
            symbol, money(info["pnl"]), info["trades"], info["wins"]))


def print_interpretation(results, strategy_m, bench_m, trade_stats):
    """Plain-English reading of the numbers."""
    print("\nINTERPRETATION")
    print("-" * 60)
    difference = (strategy_m["total_return"] - bench_m["total_return"]) * 100
    if difference >= 0:
        print("* The strategy BEAT the S&P 500 benchmark by", round(difference, 1), "percentage points.")
    else:
        print("* The strategy LAGGED the S&P 500 benchmark by", round(abs(difference), 1), "percentage points.")

    s = strategy_m["sharpe"]
    if s < 0:
        quality = "poor: it earned less than a risk-free deposit"
    elif s < 1:
        quality = "acceptable but not impressive"
    elif s < 2:
        quality = "good"
    else:
        quality = "excellent (be suspicious: very high values often mean luck or a short test)"
    print("* Sharpe ratio", num(s), "is", quality + ".")

    if strategy_m["max_dd"] > bench_m["max_dd"]:
        print("* Risk: the strategy's worst fall (" + pct(strategy_m["max_dd"]) + ") was SMALLER than the market's ("
              + pct(bench_m["max_dd"]) + ").")
    else:
        print("* Risk: the strategy's worst fall (" + pct(strategy_m["max_dd"]) + ") was LARGER than the market's ("
              + pct(bench_m["max_dd"]) + ").")

    if strategy_m["beta"] is not None:
        if strategy_m["beta"] < 0.9:
            print("* Beta", num(strategy_m["beta"]), "- less sensitive to market swings than the index.")
        elif strategy_m["beta"] > 1.1:
            print("* Beta", num(strategy_m["beta"]), "- amplifies market swings (more risky than the index).")
        else:
            print("* Beta", num(strategy_m["beta"]), "- moves roughly like the market.")
        if strategy_m["alpha"] > 0:
            print("* Alpha is positive: some return is not explained by market exposure alone.")
        else:
            print("* Alpha is not positive: the market exposure explains (or exceeds) the return.")

    if trade_stats["closed"] > 0 and trade_stats["profit_factor"] is not None:
        if trade_stats["profit_factor"] > 1:
            print("* Profit factor above 1: winning trades earned more than losing trades lost.")
        else:
            print("* Profit factor below 1: losing trades cost more than winners earned.")

    average_exposure = mean(results["invested_pct"])
    print("* On average", round(average_exposure), "% of the portfolio was invested;",
          "the largest single-stock weight reached", round(max(results["max_weight"]), 1), "%.")
    print("  (The", config.MAX_POSITION_PERCENT, "% cap is enforced when buying; a winner is trimmed back once it passes",
          config.MAX_POSITION_PERCENT + config.REBALANCE_TOLERANCE_PERCENT, "%,")
    print("   so small drifts between the checks are normal.)")

    print("\nLIMITATIONS (always state these in your presentation):")
    if results["settings"]["use_fundamentals"]:
        print("* Look-ahead bias: free APIs give TODAY'S fundamentals, so the filter used information")
        print("  that was not available at the start of the test.")
    print("* Survivorship bias: the watchlist contains stocks that are big and successful TODAY.")
    print("* A", results["settings"]["years"], "year test is a small sample; past results do not predict the future.")
    print("* Fees of", config.TRADING_COST_PERCENT, "% per trade are included, but slippage and taxes are not.")


def print_report(results):
    """The complete backtest report. Returns the summary so main.py can reuse it."""
    dates = results["dates"]
    strategy_m = compute_metrics(results["equity"], dates, results["benchmark"])
    bench_m = compute_metrics(results["benchmark"], dates, results["benchmark"])
    bench_m["beta"] = None          # comparing the benchmark with itself is meaningless
    bench_m["alpha"] = None
    bench_m["corr"] = None
    trade_stats = describe_trades(results["trades"])

    print("\n" + "=" * 60)
    print("            BACKTEST REPORT")
    print("=" * 60)
    print("Period        :", dates[0], "to", dates[-1])
    print("Start capital :", money(results["start_cash"]))
    print("Stocks traded :", ", ".join(results["stocks_tested"]))
    if len(results["rejected"]) > 0:
        names = []
        for symbol in results["rejected"]:
            names.append(symbol + " (" + results["rejected"][symbol] + ")")
        print("Excluded      :", "; ".join(names))
    print("Check frequency: every", results["settings"]["check_every"], "trading days | fundamentals filter:",
          "ON" if results["settings"]["use_fundamentals"] else "OFF")

    print_descriptive(describe_returns(results["equity"], dates), "DESCRIPTIVE ANALYSIS - strategy daily returns")
    print_descriptive(describe_returns(results["benchmark"], dates),
                      "DESCRIPTIVE ANALYSIS - benchmark (" + config.BENCHMARK_SYMBOL + ") daily returns")

    print("\nQUANTITATIVE ANALYSIS - strategy vs benchmark")
    print("-" * 60)
    print_metrics_table([("Strategy", strategy_m), (config.BENCHMARK_SYMBOL + " (hold)", bench_m)])
    print("Strategy max drawdown: peak", strategy_m["dd_peak_date"], "-> bottom", strategy_m["dd_trough_date"])

    print_trade_stats(trade_stats)

    # Where is the money at the end?
    final = results["final_portfolio"]
    prices = results["final_prices"]
    print("\nFINAL PORTFOLIO")
    print("-" * 60)
    total = results["equity"][-1]
    print("Cash:", money(final["cash"]), "(" + format(final["cash"] / total * 100, ".1f") + "%)")
    sector_value = {}
    for symbol in final["holdings"]:
        h = final["holdings"][symbol]
        value = h["shares"] * prices.get(symbol, h["avg_price"])
        sector_value[h["sector"]] = sector_value.get(h["sector"], 0) + value
        print("  {:<7}{:>6} shares   {:>10}   {:>5.1f}%   unrealised {:>+8.1f}%".format(
            symbol, h["shares"], money(value), value / total * 100,
            (prices.get(symbol, h["avg_price"]) / h["avg_price"] - 1) * 100))
    if len(sector_value) > 0:
        print("Sector exposure:")
        for sector in sector_value:
            print("  {:<24}{:>5.1f}%".format(sector, sector_value[sector] / total * 100))

    print_interpretation(results, strategy_m, bench_m, trade_stats)
    return {"strategy": strategy_m, "benchmark": bench_m, "trades": trade_stats}


# ===========================================================================
# PART 5 - ANALYSIS OF ONE STOCK
# ===========================================================================
def print_stock_statistics(symbol, history, bench_history, years):
    """Descriptive + quantitative analysis of a single stock versus the benchmark."""
    bench_close = {}
    for i in range(len(bench_history["dates"])):
        bench_close[bench_history["dates"][i]] = bench_history["close"][i]

    dates = []
    closes = []
    bench_closes = []
    for i in range(len(history["dates"])):
        day = history["dates"][i]
        if day in bench_close:                  # only days where both traded
            dates.append(day)
            closes.append(history["close"][i])
            bench_closes.append(bench_close[day])

    wanted = int(years * config.TRADING_DAYS_PER_YEAR) + 1
    dates = dates[-wanted:]
    closes = closes[-wanted:]
    bench_closes = bench_closes[-wanted:]
    if len(closes) < 60:
        print("Not enough overlapping history to analyse", symbol)
        return

    print("\n" + "=" * 60)
    print("  STATISTICS: " + symbol + "  (" + dates[0] + " to " + dates[-1] + ")")
    print("=" * 60)
    print_descriptive(describe_returns(closes, dates), "DESCRIPTIVE ANALYSIS - daily returns")

    stock_m = compute_metrics(closes, dates, bench_closes)
    bench_m = compute_metrics(bench_closes, dates)
    print("\nQUANTITATIVE ANALYSIS - " + symbol + " vs " + config.BENCHMARK_SYMBOL)
    print("-" * 60)
    print_metrics_table([(symbol, stock_m), (config.BENCHMARK_SYMBOL, bench_m)])
    print("Max drawdown: peak", stock_m["dd_peak_date"], "-> bottom", stock_m["dd_trough_date"])


# ===========================================================================
# PART 6 - FILES AND CHARTS
# ===========================================================================
def export_csv_files(results):
    """Saves the equity curve and the trade list so they can be opened in Excel."""
    os.makedirs(os.path.dirname(config.BACKTEST_EQUITY_FILE) or ".", exist_ok=True)
    with open(config.BACKTEST_EQUITY_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "strategy_value", "benchmark_value", "cash",
                         "invested_percent", "positions", "largest_weight_percent"])
        for i in range(len(results["dates"])):
            writer.writerow([results["dates"][i], round(results["equity"][i], 2),
                             round(results["benchmark"][i], 2), round(results["cash"][i], 2),
                             round(results["invested_pct"][i], 2), results["positions"][i],
                             round(results["max_weight"][i], 2)])

    with open(config.BACKTEST_TRADES_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "side", "symbol", "quantity", "price", "fee", "profit_loss",
                         "return_percent", "holding_days", "weight_after_buy_percent"])
        for t in results["trades"]:
            writer.writerow([t["date"], t["side"], t["symbol"], t["qty"], round(t["price"], 2),
                             round(t["fee"], 2), round(t["pnl"], 2), round(t["return_pct"], 2),
                             t["hold_days"], round(t["weight_after"], 2)])
    print("Saved:", config.BACKTEST_EQUITY_FILE, "and", config.BACKTEST_TRADES_FILE)


def save_charts(results, summary):
    """Draws 3 charts into one PNG image. Needs:  pip install matplotlib"""
    try:
        import matplotlib
        matplotlib.use("Agg")                  # draw to a file, no window needed
        import matplotlib.pyplot as plt
    except ImportError:
        print("Charts skipped: install matplotlib with  pip install matplotlib")
        return False

    days = []
    for d in results["dates"]:
        days.append(datetime.strptime(d, "%Y-%m-%d"))

    figure, (top, middle, bottom) = plt.subplots(3, 1, figsize=(11, 13))

    # --- Chart 1: portfolio value vs benchmark, with buy/sell markers ---
    top.plot(days, results["equity"], label="Strategy", linewidth=2)
    top.plot(days, results["benchmark"], label=config.BENCHMARK_SYMBOL + " buy & hold", linewidth=1.5)
    value_on = {}
    for i in range(len(results["dates"])):
        value_on[results["dates"][i]] = results["equity"][i]
    buy_x, buy_y, sell_x, sell_y = [], [], [], []
    for t in results["trades"]:
        if t["date"] in value_on:
            when = datetime.strptime(t["date"], "%Y-%m-%d")
            if t["side"] == "BUY":
                buy_x.append(when)
                buy_y.append(value_on[t["date"]])
            else:
                sell_x.append(when)
                sell_y.append(value_on[t["date"]])
    top.scatter(buy_x, buy_y, marker="^", color="green", s=25, label="Buy", zorder=3)
    top.scatter(sell_x, sell_y, marker="v", color="red", s=25, label="Sell", zorder=3)
    top.set_title("Portfolio value vs benchmark")
    top.set_ylabel("Value ($)")
    top.legend()
    top.grid(alpha=0.3)

    # --- Chart 2: drawdown (how far below the previous peak) ---
    middle.fill_between(days, [x * 100 for x in summary["strategy"]["drawdown_series"]], 0,
                        color="red", alpha=0.4, label="Strategy")
    middle.plot(days, [x * 100 for x in summary["benchmark"]["drawdown_series"]],
                color="black", linewidth=1, label=config.BENCHMARK_SYMBOL)
    middle.set_title("Drawdown (fall from previous peak)")
    middle.set_ylabel("%")
    middle.legend()
    middle.grid(alpha=0.3)

    # --- Chart 3: histogram of daily returns ---
    returns = [r * 100 for r in daily_returns(results["equity"])]
    bench_returns = [r * 100 for r in daily_returns(results["benchmark"])]
    bottom.hist(returns, bins=40, alpha=0.6, label="Strategy")
    bottom.hist(bench_returns, bins=40, alpha=0.4, label=config.BENCHMARK_SYMBOL)
    bottom.set_title("Distribution of daily returns")
    bottom.set_xlabel("Daily return (%)")
    bottom.set_ylabel("Number of days")
    bottom.legend()
    bottom.grid(alpha=0.3)

    figure.tight_layout()
    os.makedirs(os.path.dirname(config.BACKTEST_CHART_FILE) or ".", exist_ok=True)
    figure.savefig(config.BACKTEST_CHART_FILE, dpi=110)
    plt.close(figure)
    print("Saved chart:", config.BACKTEST_CHART_FILE)
    return True
