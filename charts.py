# Matplotlib dashboards for the simulator's tables, backtests and simulations.
# Concepts used: subplots, annotations, chart styling, file output and simple plotting.

import os
import statistics
from datetime import datetime

import matplotlib
import numpy as np
import pandas as pd

import config
import numpy_stats
import pandas_tools

if not config.SHOW_CHARTS_ON_SCREEN:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter


BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
RED = "#e34948"
GREY = "#777777"


def apply_style():
    """Applies the shared light background, grid and frame style."""
    plt.rcParams.update({"axes.facecolor": "#faf9f5", "figure.facecolor": "#faf9f5",
                         "axes.edgecolor": "#b8b8b8", "axes.grid": True,
                         "grid.color": "#d4d4d4", "grid.alpha": 0.6,
                         "axes.spines.top": False, "axes.spines.right": False})


def _finish(figure, name):
    """Saves a figure in the configured chart folder and returns its path."""
    os.makedirs(config.CHART_FOLDER, exist_ok=True)
    path = os.path.join(config.CHART_FOLDER, name + ".png")
    figure.tight_layout()
    figure.savefig(path, dpi=config.CHART_DPI, bbox_inches="tight")
    if not config.SHOW_CHARTS_ON_SCREEN:
        plt.close(figure)
    return path


def _dates(history):
    """Converts history date text to datetime values."""
    return [datetime.strptime(day, "%Y-%m-%d") for day in history["dates"]]


def _subtitle(axis, text):
    """Adds a small one-line subtitle below a chart title."""
    axis.text(0, 1.01, text, transform=axis.transAxes, fontsize=8, color=GREY)


def candlestick_dashboard(symbol, history, days=config.CANDLE_DAYS, plan=None):
    """Draws candles, volume, RSI and MACD with optional trade-plan levels."""
    apply_style()
    table = pandas_tools.add_indicators(pandas_tools.history_to_dataframe(history)).tail(days)
    figure, axes = plt.subplots(4, 1, figsize=(13, 12), sharex=True,
                                gridspec_kw={"height_ratios": [3, 1, 1, 1]})
    prices = table["close"]
    axis = axes[0]
    for i, (_, row) in enumerate(table.iterrows()):
        color = AQUA if row["close"] >= row["open"] else RED
        axis.vlines(i, row["low"], row["high"], color=color, linewidth=0.8)
        bottom = min(row["open"], row["close"])
        axis.add_patch(Rectangle((i - 0.3, bottom), 0.6,
                                 max(abs(row["close"] - row["open"]), 0.001), color=color))
    axis.plot(range(len(table)), table["sma20"], color=BLUE, linewidth=1, label="SMA20")
    axis.plot(range(len(table)), table["sma50"], color=ORANGE, linewidth=1, label="SMA50")
    axis.plot(range(len(table)), table["sma200"], color=AQUA, linewidth=1, label="SMA200")
    axis.fill_between(range(len(table)), table["bollinger_lower"].to_numpy(),
                      table["bollinger_upper"].to_numpy(), color=BLUE, alpha=0.08)
    if plan:
        if plan.get("buy_low") is not None and plan.get("buy_high") is not None:
            axis.axhspan(plan["buy_low"], plan["buy_high"], color=AQUA, alpha=0.12)
        for key, color in [("entry_price", BLUE), ("target", AQUA), ("stop", RED)]:
            if plan.get(key) is not None:
                axis.axhline(plan[key], color=color, linestyle="--", linewidth=1)
    axis.set_title(symbol + " price dashboard", loc="left")
    _subtitle(axis, "Latest close: $" + format(prices.iloc[-1], ".2f"))
    axis.set_ylabel("Price ($)")
    volume_axis = axes[1]
    volume_axis.bar(range(len(table)), table["volume"], color=GREY)
    maximum = table["volume"].max()
    volume_axis.set_ylabel("Volume")
    if maximum < 5000000:
        volume_axis.yaxis.set_major_formatter(
            FuncFormatter(lambda value, position: format(value / 1000000, ".1f") + "M"))
        volume_axis.set_ylabel("Volume (millions)")
    axes[2].plot(range(len(table)), table["rsi14"], color=ORANGE)
    axes[2].axhline(30, color=GREY, linestyle="--")
    axes[2].axhline(70, color=GREY, linestyle="--")
    axes[2].set_ylabel("RSI")
    axes[3].plot(range(len(table)), table["macd"], color=BLUE)
    axes[3].plot(range(len(table)), table["signal"], color=ORANGE)
    axes[3].bar(range(len(table)), table["histogram"], color=AQUA, alpha=0.45)
    axes[3].set_ylabel("MACD")
    axes[3].set_xlabel("Trading days")
    return _finish(figure, "candlestick_" + symbol)


def equity_dashboard(results):
    """Draws equity, drawdown, rolling Sharpe and invested percentage panels."""
    apply_style()
    table = pandas_tools.results_to_dataframe(results)
    returns = table["equity"].pct_change()
    figure, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    axes[0].plot(table.index, table["equity"], color=BLUE)
    axes[0].plot(table.index, table["benchmark"], color=ORANGE)
    values = dict(zip(results["dates"], results["equity"]))
    for trade in results.get("trades", []):
        if trade["date"] in values:
            axes[0].scatter(datetime.strptime(trade["date"], "%Y-%m-%d"), values[trade["date"]],
                            color=AQUA if trade["side"] == "BUY" else RED, s=18)
    axes[0].set_title("Strategy equity vs benchmark", loc="left")
    _subtitle(axes[0], "Final strategy value: $" + format(table["equity"].iloc[-1], ",.0f"))
    axes[0].set_ylabel("Value ($)")
    axes[1].fill_between(table.index, pandas_tools.drawdown_series(table["equity"]), 0, color=RED, alpha=.3)
    axes[1].set_ylabel("Drawdown")
    axes[2].plot(table.index, pandas_tools.rolling_sharpe(returns).fillna(0), color=AQUA)
    axes[2].set_ylabel("Rolling Sharpe")
    axes[3].plot(table.index, table["invested_pct"], color=ORANGE)
    axes[3].set_ylabel("Invested (%)")
    axes[3].set_xlabel("Date")
    return _finish(figure, "equity_dashboard")


def monthly_heatmap(results):
    """Draws monthly returns with a yearly total column."""
    apply_style()
    table = pandas_tools.monthly_returns_table(pd.Series(
        results["equity"], index=pd.to_datetime(results["dates"])))
    figure, axis = plt.subplots(figsize=(12, 6))
    values = table.to_numpy(dtype=float)
    image = axis.imshow(values, cmap="RdBu", aspect="auto", vmin=-np.nanmax(abs(values)),
                        vmax=np.nanmax(abs(values)))
    axis.set_title("Monthly strategy returns", loc="left")
    axis.set_xlabel("Month")
    axis.set_ylabel("Year")
    axis.set_xticks(range(12), ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    axis.set_yticks(range(len(table.index)), table.index)
    figure.colorbar(image, ax=axis, label="Return")
    return _finish(figure, "monthly_heatmap")


def return_distribution(values):
    """Draws a return histogram and QQ plot with a 95% VaR marker."""
    apply_style()
    returns = numpy_stats.numpy_returns(values)
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    axis = axes[0]
    axis.hist(returns, bins=30, color=BLUE, alpha=.7, label="Daily returns")
    mean = float(returns.mean()) if len(returns) else 0
    deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 1
    x = np.linspace(mean - 4 * deviation, mean + 4 * deviation, 100)
    normal = np.exp(-((x - mean) / deviation) ** 2 / 2) / (deviation * np.sqrt(2 * np.pi))
    normal = normal * len(returns) * (max(returns) - min(returns)) / 30 if len(returns) else normal
    axis.plot(x, normal, color=ORANGE, label="Normal curve")
    var = np.percentile(returns, 5) if len(returns) else 0
    axis.axvline(var, color=RED, linestyle="--", label="VaR 95%")
    axis.set_title("Return distribution", loc="left")
    axis.set_xlabel("Daily return")
    axis.set_ylabel("Days")
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    ordered = np.sort(returns)
    theoretical = [statistics.NormalDist().inv_cdf((i + .5) / len(ordered))
                   for i in range(len(ordered))] if len(ordered) else [0]
    axes[1].scatter(theoretical, ordered, color=BLUE, s=10)
    axes[1].set_title("Normal Q-Q plot", loc="left")
    axes[1].set_xlabel("Theoretical quantiles")
    axes[1].set_ylabel("Observed returns")
    return _finish(figure, "return_distribution")


def trade_analysis(results):
    """Draws realised profit, cumulative profit, stock profit and holding days."""
    apply_style()
    trades = pandas_tools.trades_to_dataframe(results.get("trades", []))
    closed = trades[trades["side"].isin(["SELL", "TRIM"])] if not trades.empty else trades
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    if not closed.empty:
        axes[0, 0].bar(range(len(closed)), closed["pnl"], color=[AQUA if x >= 0 else RED for x in closed["pnl"]])
        axes[0, 1].plot(range(len(closed)), closed["pnl"].cumsum(), color=BLUE)
        axes[1, 0].bar(closed.groupby("symbol")["pnl"].sum().index,
                       closed.groupby("symbol")["pnl"].sum().values, color=ORANGE)
        axes[1, 1].bar(range(len(closed)), closed["hold_days"], color=GREY)
    axes[0, 0].set_title("Profit per trade", loc="left")
    axes[0, 1].set_title("Cumulative profit", loc="left")
    axes[1, 0].set_title("Profit by stock", loc="left")
    axes[1, 1].set_title("Holding days", loc="left")
    return _finish(figure, "trade_analysis")


def plan_outcomes_chart(plans):
    """Draws counts of trade-plan outcomes."""
    apply_style()
    counts = {}
    for plan in plans:
        outcome = plan.get("outcome") or plan.get("status") or "unknown"
        counts[outcome] = counts.get(outcome, 0) + 1
    figure, axis = plt.subplots(figsize=(9, 5))
    names = list(counts)
    bars = axis.barh(names, [counts[name] for name in names], color=BLUE)
    for bar in bars:
        axis.text(bar.get_width() + .1, bar.get_y() + bar.get_height() / 2,
                  str(int(bar.get_width())), va="center", backgroundcolor="#faf9f5")
    axis.set_title("Trade-plan outcomes", loc="left")
    axis.set_xlabel("Plans")
    return _finish(figure, "plan_outcomes")


def allocation_charts(portfolio, prices):
    """Draws stock allocation and sector allocation including cash."""
    apply_style()
    table, total = pandas_tools.portfolio_to_dataframe(portfolio, prices)
    stocks = table[table["symbol"] != "CASH"]
    sectors = table.groupby("sector")["weight_%"].sum()
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    bars = axes[0].bar(stocks["symbol"], stocks["weight_%"], color=BLUE)
    axes[0].axhline(config.MAX_POSITION_PERCENT, color=RED, linestyle="--")
    for bar, high in zip(bars, stocks["high_concentration"]):
        label = "HIGH CONCENTRATION" if high else format(bar.get_height(), ".1f") + "%"
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + .2, label,
                     ha="center", fontsize=7, color=RED if high else GREY,
                     backgroundcolor="#faf9f5")
    axes[0].set_title("Stock allocation", loc="left")
    axes[0].set_ylabel("Weight (%)")
    axes[1].bar(sectors.index, sectors.values, color=AQUA)
    axes[1].set_title("Sector allocation including cash", loc="left")
    axes[1].set_ylabel("Weight (%)")
    axes[1].tick_params(axis="x", rotation=45)
    return _finish(figure, "allocation_charts")


def monte_carlo_chart(sim):
    """Draws simulated value bands and the distribution of ending values."""
    apply_style()
    paths = sim["paths"]
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    x = range(paths.shape[1])
    axes[0].fill_between(x, np.percentile(paths, 5, axis=0), np.percentile(paths, 95, axis=0),
                         color=BLUE, alpha=.15)
    axes[0].fill_between(x, np.percentile(paths, 25, axis=0), np.percentile(paths, 75, axis=0),
                         color=BLUE, alpha=.3)
    axes[0].plot(x, np.percentile(paths, 50, axis=0), color=BLUE)
    axes[0].set_title("Monte Carlo fan chart", loc="left")
    axes[0].set_xlabel("Days")
    axes[0].set_ylabel("Value ($)")
    axes[1].hist(sim["end_values"], bins=30, color=ORANGE)
    axes[1].set_title("Ending values", loc="left")
    axes[1].set_xlabel("Value ($)")
    return _finish(figure, "monte_carlo")


def frontier_chart(result, closes):
    """Draws the random portfolio risk-return frontier and three selected portfolios."""
    apply_style()
    frame = result["portfolios"]
    figure, axis = plt.subplots(figsize=(10, 6))
    if not frame.empty:
        axis.scatter(frame["volatility"], frame["return"], c=frame["sharpe"], cmap="viridis",
                     s=7, alpha=.35)
    for name, color, marker in [("best_sharpe", RED, "*"), ("lowest_risk", AQUA, "D"),
                                ("equal_weight", ORANGE, "X")]:
        row = result.get(name)
        if row:
            axis.scatter(row["volatility"], row["return"], color=color, marker=marker, s=100)
            axis.annotate(name, (row["volatility"], row["return"]))
    axis.set_title("Random portfolio frontier", loc="left")
    _subtitle(axis, "Higher return and lower risk are preferred")
    axis.set_xlabel("Annual volatility")
    axis.set_ylabel("Annual return")
    axis.margins(x=0.12)
    return _finish(figure, "frontier")


def correlation_heatmap(correlation):
    """Draws a labelled red-white-blue correlation heatmap."""
    apply_style()
    names = list(correlation.columns)
    longest = max([len(name) for name in names] + [5])
    figure, axis = plt.subplots(figsize=(max(7, len(names) * .8), max(6, len(names) * .7)))
    cmap = LinearSegmentedColormap.from_list("correlation", [RED, "white", BLUE])
    image = axis.imshow(correlation.to_numpy(), cmap=cmap, vmin=-1, vmax=1)
    axis.set_xticks(range(len(names)), names, rotation=90)
    axis.set_yticks(range(len(names)), names)
    for row in range(len(names)):
        for column in range(len(names)):
            axis.text(column, row, format(correlation.iloc[row, column], ".2f"),
                      ha="center", va="center", fontsize=8)
    axis.set_title("Return correlation", loc="left")
    figure.colorbar(image, ax=axis, fraction=.046, pad=.04)
    figure.subplots_adjust(bottom=min(.45, .16 + longest * .012), right=.88)
    return _finish(figure, "correlation_heatmap")


def normalised_prices_chart(closes, stats):
    """Draws growth of 100 invested and highlights the three best stocks."""
    apply_style()
    normalised = closes / closes.iloc[0] * 100
    ranking = list(stats["symbol"])[:3] if not stats.empty and "symbol" in stats else []
    figure, axis = plt.subplots(figsize=(12, 6))
    for symbol in normalised.columns:
        axis.plot(normalised.index, normalised[symbol],
                  color=BLUE if symbol in ranking else GREY,
                  linewidth=2 if symbol in ranking else .8,
                  alpha=1 if symbol in ranking else .35)
        if symbol in ranking:
            axis.text(normalised.index[-1], normalised[symbol].iloc[-1], symbol)
    axis.set_title("Normalised price growth", loc="left")
    axis.set_xlabel("Date")
    axis.set_ylabel("Value of $100")
    return _finish(figure, "normalised_prices")


def fundamentals_scorecard(raw, verdict):
    """Draws every fundamental rule with actual values and a score bar."""
    apply_style()
    figure, axes = plt.subplots(2, 1, figsize=(12, max(5, len(verdict["details"]) * .45 + 3)),
                                gridspec_kw={"height_ratios": [4, 1]})
    labels = [detail[0] for detail in verdict["details"]]
    values = [detail[1] for detail in verdict["details"]]
    colours = [AQUA if detail[2] else RED for detail in verdict["details"]]
    axes[0].barh(labels, range(len(labels)), color=colours)
    for i, value in enumerate(values):
        axes[0].text(i + .05, i, format(value, ".3g") if isinstance(value, float) else str(value),
                     va="center", backgroundcolor="#faf9f5")
    axes[0].set_title(raw.get("symbol", "Company") + " fundamentals scorecard", loc="left")
    axes[0].set_xlabel("Rule result")
    axes[1].barh(["Score"], [verdict["score_percent"]], color=BLUE)
    axes[1].axvline(config.FUNDAMENTAL_PASS_PERCENT, color=RED, linestyle="--")
    axes[1].set_xlim(0, 100)
    axes[1].set_xlabel("Pass percentage")
    return _finish(figure, "fundamentals_scorecard_" + str(raw.get("symbol", "company")))


def fundamentals_peer_chart(table):
    """Draws six simple peer-comparison metric bar charts."""
    metrics = ["roe", "operating_margin", "revenue_growth", "pe", "pbv", "debt_to_equity"]
    figure, axes = plt.subplots(2, 3, figsize=(14, 8))
    for axis, metric in zip(axes.flat, metrics):
        if metric in table:
            axis.bar(table["symbol"], table[metric], color=BLUE)
        axis.set_title(metric, loc="left")
        axis.tick_params(axis="x", rotation=45)
    return _finish(figure, "fundamentals_peers")


def write_gallery(paths, title):
    """Writes a plain HTML index linking to all generated chart images."""
    os.makedirs(config.CHART_FOLDER, exist_ok=True)
    path = os.path.join(config.CHART_FOLDER, "index.html")
    with open(path, "w", encoding="utf-8") as file:
        file.write("<html><head><title>" + title + "</title></head><body>\n")
        file.write("<h1>" + title + "</h1>\n")
        for chart_path in paths:
            file.write("<p><a href='" + os.path.basename(chart_path) + "'>"
                       + os.path.basename(chart_path) + "</a></p>\n")
        file.write("</body></html>\n")
    return path


def backtest_chart_pack(results):
    """Prints library reports, runs simulations and creates the backtest chart gallery."""
    tables = pandas_tools.print_pandas_report(results)
    verification = numpy_stats.verify_metrics(results["equity"], results["dates"])
    numpy_stats.print_verification(verification, "Backtest metrics verification")
    simulation = numpy_stats.monte_carlo(results["equity"], config.MONTE_CARLO_DAYS,
                                         config.MONTE_CARLO_PATHS)
    numpy_stats.print_monte_carlo(simulation)
    paths = [equity_dashboard(results), monthly_heatmap(results),
             return_distribution(results["equity"]), trade_analysis(results)]
    paths.append(monte_carlo_chart(simulation))
    paths.append(allocation_charts(results["final_portfolio"], results["final_prices"]))
    paths.append(plan_outcomes_chart(results.get("plans") or []))
    return write_gallery(paths, "Backtest analysis gallery")
