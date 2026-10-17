"""Streamlit dashboard for the portfolio and stock-analysis simulator."""

import csv
import os

import pandas as pd
import streamlit as st

import analytics
import backtester
import charts
import config
import data_fetcher
import fundamentals
import numpy_stats
import pandas_tools
import portfolio as pf
import strategy
import technicals


st.set_page_config(
    page_title="Portfolio & Trading Simulator",
    page_icon="📈",
    layout="wide",
)


def load_watchlist():
    if not os.path.exists(config.WATCHLIST_FILE):
        return []
    with open(config.WATCHLIST_FILE, encoding="utf-8") as file:
        return [
            line.strip().upper()
            for line in file
            if line.strip() and not line.strip().startswith("#")
        ]


def cached_price(symbol, fallback=None):
    history = data_fetcher.get_price_history(symbol, use_disk_cache=True)
    if history and history["close"]:
        return float(history["close"][-1])
    return fallback


def portfolio_frame(portfolio, prices):
    rows = []
    total = pf.get_total_value(portfolio, prices)
    for symbol, holding in portfolio["holdings"].items():
        price = prices.get(symbol, holding["avg_price"])
        value = holding["shares"] * price
        rows.append(
            {
                "Symbol": symbol,
                "Sector": holding.get("sector", "Unknown"),
                "Shares": holding["shares"],
                "Average cost": holding["avg_price"],
                "Price": price,
                "Value": value,
                "Allocation %": value / total * 100 if total else 0,
                "P/L %": (price / holding["avg_price"] - 1) * 100,
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=600, show_spinner=False)
def load_stock_analysis(symbol):
    raw = data_fetcher.get_fundamental_data(symbol, use_disk_cache=True)
    history = data_fetcher.get_price_history(symbol, use_disk_cache=True)
    if raw is None or history is None:
        return None
    fund = fundamentals.analyze_fundamentals(raw)
    tech = technicals.analyze_technicals(history)
    action = "REJECT" if not fund["passed"] else tech["signal"]
    return {"raw": raw, "history": history, "fund": fund, "tech": tech, "action": action}


def show_dashboard():
    st.header("Portfolio dashboard")
    portfolio = pf.load_portfolio()
    symbols = list(portfolio["holdings"])
    prices = {symbol: cached_price(symbol, holding["avg_price"])
              for symbol, holding in portfolio["holdings"].items()}
    total = pf.get_total_value(portfolio, prices)
    invested = pf.get_holdings_value(portfolio, prices)

    cash_col, invested_col, total_col, holdings_col = st.columns(4)
    cash_col.metric("Cash", f"${portfolio['cash']:,.2f}")
    invested_col.metric("Invested", f"${invested:,.2f}")
    total_col.metric("Total value", f"${total:,.2f}")
    holdings_col.metric("Holdings", len(symbols))

    if symbols:
        frame = portfolio_frame(portfolio, prices)
        st.subheader("Holdings")
        st.dataframe(
            frame.style.format(
                {"Average cost": "${:,.2f}", "Price": "${:,.2f}", "Value": "${:,.2f}",
                 "Allocation %": "{:.2f}%", "P/L %": "{:+.2f}%"}
            ),
            use_container_width=True,
            hide_index=True,
        )
        chart = frame.set_index("Symbol")["Value"]
        st.bar_chart(chart)
    else:
        st.info("No holdings yet. Use the Stock analysis page to inspect symbols, or run the CLI starter-portfolio flow.")

    if portfolio.get("pending_orders"):
        st.subheader("Pending orders")
        st.dataframe(pd.DataFrame(portfolio["pending_orders"]), use_container_width=True, hide_index=True)


def show_stock_analysis():
    st.header("Stock analysis")
    default = load_watchlist()[0] if load_watchlist() else "AAPL"
    symbol = st.text_input("Ticker symbol", default).strip().upper()
    if not symbol:
        return
    if st.button("Analyze", type="primary"):
        st.session_state["analysis_symbol"] = symbol
    symbol = st.session_state.get("analysis_symbol", symbol)

    with st.spinner(f"Loading {symbol}..."):
        result = load_stock_analysis(symbol)
    if result is None:
        st.error("Could not load data. Check the ticker or add cached files in data/cache.")
        return

    raw, fund, tech = result["raw"], result["fund"], result["tech"]
    action = result["action"]
    st.metric("Decision", action, f"{raw.get('name') or symbol} · {fund['sector']}")
    st.caption("Educational simulation only; this is not financial advice.")

    left, right = st.columns(2)
    with left:
        st.subheader("Fundamentals")
        st.progress(min(fund["score_percent"] / 100, 1.0))
        st.write(f"**Score:** {fund['passed_rules']}/{fund['checked_rules']} ({fund['score_percent']:.0f}%)")
        st.write(f"**Verdict:** {'PASS' if fund['passed'] else 'REJECTED'} — {fund['reason']}")
        details = pd.DataFrame(fund["details"], columns=["Rule", "Actual", "Passed"])
        if not details.empty:
            st.dataframe(details, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Technicals")
        st.metric("Signal", tech["signal"], f"Score {tech['score']}")
        indicators = tech["indicators"]
        indicator_rows = [
            ("Price", tech["price"]), ("SMA 20", indicators["sma20"]),
            ("SMA 50", indicators["sma50"]), ("SMA 200", indicators["sma200"]),
            ("RSI", indicators["rsi"]), ("Stochastic", indicators["stoch"]),
            ("Volume ratio", indicators["volume_ratio"]),
        ]
        st.dataframe(pd.DataFrame(indicator_rows, columns=["Indicator", "Value"]),
                     use_container_width=True, hide_index=True)
        if tech["states"]:
            st.write("**States:** " + " · ".join(tech["states"]))
        if tech["patterns"]:
            st.write("**Patterns:** " + " · ".join(tech["patterns"]))

    history = result["history"]
    chart = pd.DataFrame({"Close": history["close"]}, index=pd.to_datetime(history["dates"]))
    st.subheader("Price history")
    st.line_chart(chart)
    st.subheader("Technical dashboard")
    st.caption("Price candles, volume, moving averages, Bollinger Bands, RSI and MACD.")
    technical_chart = charts.candlestick_dashboard(symbol, history, config.CANDLE_DAYS)
    st.image(technical_chart, use_container_width=True)
    with st.expander("Score reasoning"):
        for reason in tech["reasons"]:
            st.write(reason)


def show_backtest():
    st.header("Backtest")
    symbols = load_watchlist()
    if not symbols:
        st.warning("watchlist.txt is empty.")
        return
    selected = st.multiselect("Stocks", symbols, default=symbols)
    years = st.slider("Years to replay", 0.5, 10.0, float(config.BACKTEST_YEARS), 0.5)
    cash = st.number_input("Starting cash", min_value=100.0, value=float(config.STARTING_CASH), step=1000.0)
    every = st.number_input("Analyze every N trading days", min_value=1, value=config.BACKTEST_CHECK_EVERY_DAYS)
    use_fundamentals = st.checkbox("Apply fundamentals filter", True)
    use_cache = st.checkbox("Use saved cache (offline)", True)

    if st.button("Run backtest", type="primary", disabled=not selected):
        with st.spinner("Replaying historical data..."):
            results = backtester.run_backtest(
                selected, years, cash, every, use_fundamentals, use_cache
            )
        if results is None:
            st.error("Backtest could not load the benchmark or stock data.")
            return
        st.session_state["backtest_results"] = results

    results = st.session_state.get("backtest_results")
    if not results:
        st.info("Configure the test and click Run backtest.")
        return
    strategy_metrics = analytics.compute_metrics(results["equity"], results["dates"], results["benchmark"])
    benchmark_metrics = analytics.compute_metrics(results["benchmark"], results["dates"])
    a, b, c = st.columns(3)
    a.metric("Strategy return", f"{strategy_metrics['total_return']:.2%}")
    b.metric("SPY return", f"{benchmark_metrics['total_return']:.2%}")
    c.metric("Max drawdown", f"{strategy_metrics['max_dd']:.2%}")
    curve = pd.DataFrame(
        {"Strategy": results["equity"], config.BENCHMARK_SYMBOL: results["benchmark"]},
        index=pd.to_datetime(results["dates"]),
    )
    st.line_chart(curve)
    st.dataframe(
        pd.DataFrame(
            {
                "Metric": ["CAGR", "Volatility", "Sharpe", "Sortino", "Beta", "Correlation"],
                "Strategy": [strategy_metrics["cagr"], strategy_metrics["volatility"],
                             strategy_metrics["sharpe"], strategy_metrics["sortino"],
                             strategy_metrics["beta"], strategy_metrics["corr"]],
                "Benchmark": [benchmark_metrics["cagr"], benchmark_metrics["volatility"],
                              benchmark_metrics["sharpe"], benchmark_metrics["sortino"], None, None],
            }
        ).style.format({"Strategy": "{:.2f}", "Benchmark": "{:.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
    if results["trades"]:
        st.subheader("Simulated trades")
        st.dataframe(pd.DataFrame(results["trades"]), use_container_width=True, hide_index=True)


def show_statistics():
    st.header("Stock statistics")
    symbol = st.text_input("Ticker", "AAPL", key="statistics_symbol").strip().upper()
    years = st.slider("History", 1, 10, 3, key="statistics_years")
    if st.button("Calculate statistics", type="primary"):
        history = data_fetcher.get_price_history(symbol, True)
        benchmark = data_fetcher.get_price_history(config.BENCHMARK_SYMBOL, True)
        if history is None or benchmark is None:
            st.error("Not enough cached or downloadable data.")
            return
        bench_by_date = dict(zip(benchmark["dates"], benchmark["close"]))
        dates, closes, bench_closes = [], [], []
        for date, close in zip(history["dates"], history["close"]):
            if date in bench_by_date:
                dates.append(date)
                closes.append(close)
                bench_closes.append(bench_by_date[date])
        wanted = years * config.TRADING_DAYS_PER_YEAR + 1
        dates, closes, bench_closes = dates[-wanted:], closes[-wanted:], bench_closes[-wanted:]
        if len(closes) < 60:
            st.error("At least 60 overlapping trading days are required.")
            return
        stock = analytics.compute_metrics(closes, dates, bench_closes)
        benchmark_metrics = analytics.compute_metrics(bench_closes, dates)
        st.session_state["statistics"] = (stock, benchmark_metrics, dates, closes, bench_closes)
    if "statistics" not in st.session_state:
        st.info("Choose a ticker and calculate its statistics.")
        return
    stock, benchmark_metrics, dates, closes, bench_closes = st.session_state["statistics"]
    st.dataframe(pd.DataFrame({
        "Metric": ["Total return", "CAGR", "Volatility", "Sharpe", "Sortino", "Max drawdown", "Beta", "Correlation"],
        symbol: [stock["total_return"], stock["cagr"], stock["volatility"], stock["sharpe"],
                 stock["sortino"], stock["max_dd"], stock["beta"], stock["corr"]],
        config.BENCHMARK_SYMBOL: [benchmark_metrics["total_return"], benchmark_metrics["cagr"],
                                  benchmark_metrics["volatility"], benchmark_metrics["sharpe"],
                                  benchmark_metrics["sortino"], None, None, None],
    }).style.format({symbol: "{:.2f}", config.BENCHMARK_SYMBOL: "{:.2f}"}),
                 use_container_width=True, hide_index=True)
    st.line_chart(pd.DataFrame({symbol: closes, config.BENCHMARK_SYMBOL: bench_closes},
                               index=pd.to_datetime(dates)))


def show_library_analysis():
    """Expose the CLI's pandas, NumPy and Matplotlib analysis in Streamlit."""
    st.header("Library analysis")
    st.caption("These views use the same pandas, NumPy and Matplotlib functions as the CLI.")

    tabs = st.tabs(["Watchlist", "Monte Carlo", "Portfolio", "Fundamentals"])

    with tabs[0]:
        st.subheader("Watchlist analysis")
        years = st.slider("Years of watchlist history", 1, 10, config.BACKTEST_YEARS,
                          key="library_watchlist_years")
        closes = pandas_tools.load_close_table(load_watchlist(), years, True)
        if closes.empty or len(closes.columns) < 2:
            st.warning("At least two cached watchlist price histories are required.")
        else:
            stats = pandas_tools.watchlist_statistics(closes)
            st.dataframe(stats, use_container_width=True, hide_index=True)
            correlation = pandas_tools.correlation_table(closes)
            result = numpy_stats.random_portfolios(closes, config.RANDOM_PORTFOLIOS)
            chart_columns = st.columns(3)
            with chart_columns[0]:
                st.image(charts.frontier_chart(result, closes), use_container_width=True)
            with chart_columns[1]:
                st.image(charts.correlation_heatmap(correlation), use_container_width=True)
            with chart_columns[2]:
                st.image(charts.normalised_prices_chart(closes, stats), use_container_width=True)
            with st.expander("Selected portfolio weights"):
                for name in ["best_sharpe", "lowest_risk", "equal_weight"]:
                    row = result.get(name)
                    if row:
                        st.write(name.replace("_", " ").title(), row)

    with tabs[1]:
        st.subheader("Monte Carlo simulation")
        symbol = st.text_input("Ticker for simulation", "AAPL",
                               key="library_monte_carlo_symbol").strip().upper()
        days = st.slider("Simulation days", 30, 756, config.MONTE_CARLO_DAYS,
                         key="library_monte_carlo_days")
        paths = st.slider("Simulation paths", 100, 5000, config.MONTE_CARLO_PATHS, step=100,
                          key="library_monte_carlo_paths")
        history = data_fetcher.get_price_history(symbol, True) if symbol else None
        if history is None or len(history["close"]) < 2:
            st.warning("A cached price history with at least two observations is required.")
        else:
            simulation = numpy_stats.monte_carlo(history["close"], days, paths)
            metrics = pd.DataFrame({
                "Metric": ["Starting value", "5th percentile", "Median", "95th percentile",
                           "Chance of loss", "Chance of gain over 10%"],
                "Value": [
                    simulation["start_value"], simulation["percentiles"]["5"],
                    simulation["percentiles"]["50"], simulation["percentiles"]["95"],
                    simulation["chance_loss"], simulation["chance_gain_10"],
                ],
            })
            st.dataframe(metrics.style.format({"Value": "{:.2%}"}), use_container_width=True,
                         hide_index=True)
            st.image(charts.monte_carlo_chart(simulation), use_container_width=True)

    with tabs[2]:
        st.subheader("Current portfolio allocation")
        portfolio = pf.load_portfolio()
        if not portfolio["holdings"]:
            st.info("The portfolio has no holdings to chart.")
        else:
            prices = {symbol: cached_price(symbol, holding["avg_price"])
                      for symbol, holding in portfolio["holdings"].items()}
            table, total = pandas_tools.portfolio_to_dataframe(portfolio, prices)
            st.metric("Total portfolio value", f"${total:,.2f}")
            st.dataframe(table.style.format({
                "avg_price": "${:,.2f}", "price": "${:,.2f}", "value": "${:,.2f}",
                "weight_%": "{:.2f}%",
            }), use_container_width=True, hide_index=True)
            st.image(charts.allocation_charts(portfolio, prices), use_container_width=True)

    with tabs[3]:
        st.subheader("Fundamentals charts")
        symbols = load_watchlist()
        symbol = st.selectbox("Company", symbols or ["AAPL"],
                              key="library_fundamentals_symbol")
        raw = data_fetcher.get_fundamental_data(symbol, True)
        peers = pandas_tools.fundamentals_table(symbols, True)
        if raw is None:
            st.warning("Fundamental data is not available in the cache.")
        else:
            verdict = fundamentals.analyze_fundamentals(raw)
            st.dataframe(pd.DataFrame(verdict["details"],
                                      columns=["Rule", "Actual", "Passed"]),
                         use_container_width=True, hide_index=True)
            st.image(charts.fundamentals_scorecard(raw, verdict), use_container_width=True)
            if not peers.empty:
                st.image(charts.fundamentals_peer_chart(peers), use_container_width=True)


def show_backtest_charts(results):
    """Render the extended chart pack for a completed backtest."""
    with st.expander("Extended backtest analysis", expanded=True):
        chart_columns = st.columns(2)
        chart_paths = [
            charts.equity_dashboard(results),
            charts.monthly_heatmap(results),
            charts.return_distribution(results["equity"]),
            charts.trade_analysis(results),
            charts.monte_carlo_chart(
                numpy_stats.monte_carlo(results["equity"], config.MONTE_CARLO_DAYS,
                                        config.MONTE_CARLO_PATHS)
            ),
            charts.allocation_charts(results["final_portfolio"], results["final_prices"]),
            charts.plan_outcomes_chart(results.get("plans") or []),
        ]
        for index, path in enumerate(chart_paths):
            with chart_columns[index % 2]:
                st.image(path, use_container_width=True)


def show_trade_history():
    st.header("Trade history")
    path = config.TRADES_FILE
    if not os.path.exists(path):
        st.info("No trades have been recorded yet.")
        return
    with open(path, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


st.sidebar.title("Simulator")
st.sidebar.caption("Virtual money only")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Stock analysis", "Backtest", "Stock statistics", "Trade history"],
)
if page == "Dashboard":
    show_dashboard()
elif page == "Stock analysis":
    show_stock_analysis()
elif page == "Backtest":
    show_backtest()
elif page == "Stock statistics":
    show_statistics()
else:
    show_trade_history()
