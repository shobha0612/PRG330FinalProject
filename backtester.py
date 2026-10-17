# backtester.py
# MODULE 9 - Replays the past, day by day, as if the simulator had been running then.
# Concepts used: for loops, dictionaries, lists, slicing, functions, datetime
#
# Why? The live simulator only trades while the US market is open. A backtest
# needs no open market: it uses OLD prices, so it works any time (even offline).
#
# For every historical day the backtester does what the live system does:
#   1. Fills yesterday's queued orders at TODAY'S OPEN price.
#   2. Every few days, analyses each stock using ONLY data up to today's close
#      (technicals module) and queues BUY / SELL orders for the next open.
#   3. Obeys the SAME 5% cap and cash reserve (risk_manager module); winners that
#      grow past the cap are trimmed back.
#   4. Records the portfolio value at today's close.
#
# Orders are queued after the close and filled at the next open, exactly like
# the live "pending orders" idea. This avoids "peeking at tomorrow's price".

import time
from datetime import datetime, timedelta

import config
import data_fetcher
import fundamentals
import technicals
import risk_manager
import portfolio as pf


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def days_between(date_a, date_b):
    """Number of calendar days between two 'YYYY-MM-DD' texts."""
    a = datetime.strptime(date_a, "%Y-%m-%d")
    b = datetime.strptime(date_b, "%Y-%m-%d")
    return (b - a).days


def slice_history(history, end_index):
    """The part of a stock's history up to (and including) end_index. NO future data."""
    stop = end_index + 1
    return {
        "open": history["open"][:stop],
        "high": history["high"][:stop],
        "low": history["low"][:stop],
        "close": history["close"][:stop],
        "volume": history["volume"][:stop],
    }


def find_start_index(dates, years):
    """Index of the first benchmark date inside the last `years` years."""
    last_day = datetime.strptime(dates[-1], "%Y-%m-%d")
    start_text = (last_day - timedelta(days=int(365.25 * years))).strftime("%Y-%m-%d")
    for i in range(len(dates)):
        if dates[i] >= start_text:
            return i
    return 0


# ---------------------------------------------------------------------------
# Simulated buying and selling (these never touch your real portfolio files)
# ---------------------------------------------------------------------------
def simulate_buy(portfolio, trades, date, symbol, qty, price, sector):
    cost = qty * price
    fee = cost * config.TRADING_COST_PERCENT / 100
    if qty <= 0 or cost + fee > portfolio["cash"]:
        return False

    holdings = portfolio["holdings"]
    if symbol in holdings:
        old = holdings[symbol]
        total_shares = old["shares"] + qty
        old["avg_price"] = (old["shares"] * old["avg_price"] + cost + fee) / total_shares
        old["shares"] = total_shares
    else:
        holdings[symbol] = {"shares": qty, "avg_price": (cost + fee) / qty,
                            "sector": sector, "buy_date": date}
    portfolio["cash"] = portfolio["cash"] - cost - fee

    trades.append({"date": date, "side": "BUY", "symbol": symbol, "qty": qty,
                   "price": price, "fee": fee, "pnl": 0.0, "return_pct": 0.0,
                   "hold_days": 0, "sector": sector, "weight_after": 0.0})
    return True


def simulate_sell(portfolio, trades, date, symbol, price, qty=None, side="SELL"):
    """
    Sells the whole position (qty=None) or just some shares (a "TRIM" back to the 5% cap).
    Records the profit/loss of what was sold.
    """
    holding = portfolio["holdings"][symbol]
    if qty is None or qty > holding["shares"]:
        qty = holding["shares"]
    proceeds = qty * price
    fee = proceeds * config.TRADING_COST_PERCENT / 100
    cost_basis = qty * holding["avg_price"]
    pnl = proceeds - fee - cost_basis

    portfolio["cash"] = portfolio["cash"] + proceeds - fee
    trades.append({"date": date, "side": side, "symbol": symbol, "qty": qty,
                   "price": price, "fee": fee, "pnl": pnl,
                   "return_pct": pnl / cost_basis * 100,
                   "hold_days": days_between(holding["buy_date"], date),
                   "sector": holding["sector"], "weight_after": 0.0})
    if qty == holding["shares"]:
        del portfolio["holdings"][symbol]
    else:
        holding["shares"] = holding["shares"] - qty
    return True


# ---------------------------------------------------------------------------
# Loading the stocks we will test
# ---------------------------------------------------------------------------
def load_universe(symbols, use_fundamentals, use_disk_cache):
    """
    Downloads (or reads from disk) prices and fundamentals for each symbol.
    Returns (stocks, rejected):
        stocks   = {symbol: {"history":..., "index": {date: position}, "sector":...}}
        rejected = {symbol: reason}
    NOTE: free APIs only give TODAY'S fundamentals, so the fundamentals filter
    looks at the present, not at the past. This is "look-ahead bias" and we
    explain it in the final report.
    """
    stocks = {}
    rejected = {}
    for symbol in symbols:
        history = data_fetcher.get_price_history(symbol, use_disk_cache)
        if history is None:
            rejected[symbol] = "no price data"
            continue

        raw = data_fetcher.get_fundamental_data(symbol, use_disk_cache)
        sector = "Unknown"
        if raw is not None:
            fund = fundamentals.analyze_fundamentals(raw)
            sector = fund["sector"]
            if use_fundamentals and not fund["passed"]:
                rejected[symbol] = fund["reason"]
                continue
        elif use_fundamentals:
            rejected[symbol] = "no fundamental data"
            continue

        index_by_date = {}
        for i in range(len(history["dates"])):
            index_by_date[history["dates"][i]] = i
        stocks[symbol] = {"history": history, "index": index_by_date, "sector": sector}
    return stocks, rejected


# ---------------------------------------------------------------------------
# The backtest itself
# ---------------------------------------------------------------------------
def run_backtest(symbols, years=None, start_cash=None, check_every=None,
                 use_fundamentals=True, use_disk_cache=True):
    """
    Replays the strategy over the last `years` years.
    Returns a results dictionary (or None if the benchmark could not be loaded).
    """
    if years is None:
        years = config.BACKTEST_YEARS
    if start_cash is None:
        start_cash = config.STARTING_CASH
    if check_every is None:
        check_every = config.BACKTEST_CHECK_EVERY_DAYS

    # ----- 1. The calendar comes from the benchmark (SPY) -----
    benchmark = data_fetcher.get_price_history(config.BENCHMARK_SYMBOL, use_disk_cache)
    if benchmark is None:
        print("Could not load the benchmark", config.BENCHMARK_SYMBOL)
        return None
    first = find_start_index(benchmark["dates"], years)
    calendar = benchmark["dates"][first:]
    bench_closes = benchmark["close"][first:]
    print("Test period:", calendar[0], "to", calendar[-1], "(" + str(len(calendar)) + " trading days)")

    # ----- 2. Load the stocks (and apply the fundamentals filter) -----
    print("Loading stocks...")
    stocks, rejected = load_universe(symbols, use_fundamentals, use_disk_cache)
    if len(stocks) == 0:
        print("No stocks left to trade.")
        return None
    print("Tradable stocks:", len(stocks), "| Rejected by fundamentals/data:", len(rejected))

    # ----- 3. Day-by-day replay -----
    portfolio = {"cash": start_cash, "holdings": {}, "pending_orders": []}
    trades = []
    queue = []                    # orders waiting for the next open: (side, symbol)
    last_close = {}               # latest known close of every stock
    result_dates = []
    equity_curve = []
    cash_curve = []
    invested_curve = []
    positions_curve = []
    max_weight_curve = []

    print("Replaying history", end="", flush=True)
    for day_number in range(len(calendar)):
        date = calendar[day_number]
        if day_number % 50 == 0:
            print(".", end="", flush=True)

        # --- (a) Fill queued orders at today's OPEN (sells first, so cash is freed) ---
        queue.sort(key=lambda order: 1 if order[0] == "BUY" else 0)
        for side, symbol in queue:
            stock = stocks[symbol]
            i = stock["index"].get(date)
            if i is None:
                continue                                  # stock did not trade today
            open_price = stock["history"]["open"][i]
            if side == "SELL":
                if symbol in portfolio["holdings"]:
                    simulate_sell(portfolio, trades, date, symbol, open_price)
            elif side == "TRIM":
                excess = risk_manager.shares_to_trim(portfolio, symbol, open_price, last_close)
                if excess > 0:
                    simulate_sell(portfolio, trades, date, symbol, open_price, excess, "TRIM")
            else:
                wanted = risk_manager.max_shares_under_cap(portfolio, symbol, open_price, last_close)
                qty, messages, warning = risk_manager.validate_buy(
                    portfolio, symbol, wanted, open_price, last_close, "auto")
                if qty > 0 and simulate_buy(portfolio, trades, date, symbol, qty,
                                            open_price, stock["sector"]):
                    # remember how big the position is right after buying (to prove the 5% cap)
                    total = pf.get_total_value(portfolio, last_close)
                    trades[-1]["weight_after"] = pf.get_position_value(
                        portfolio, symbol, last_close) / total * 100
        queue = []

        # --- (b) Update closing prices ---
        for symbol in stocks:
            i = stocks[symbol]["index"].get(date)
            if i is not None:
                last_close[symbol] = stocks[symbol]["history"]["close"][i]

        # --- (c) Decide (using data up to today's close only) ---
        is_check_day = day_number % check_every == 0
        is_last_day = day_number == len(calendar) - 1
        if is_check_day and not is_last_day:
            for symbol in stocks:
                stock = stocks[symbol]
                i = stock["index"].get(date)
                if i is None or i + 1 < config.MIN_CANDLES_FOR_ANALYSIS:
                    continue                              # not enough history yet
                tech = technicals.analyze_technicals(slice_history(stock["history"], i))
                owned = symbol in portfolio["holdings"]
                if tech["signal"] == "BUY":
                    queue.append(("BUY", symbol))
                elif tech["signal"] == "SELL" and owned:
                    queue.append(("SELL", symbol))
                # A winner that grew past the 5% cap is trimmed back
                if owned and tech["signal"] != "SELL":
                    if risk_manager.shares_to_trim(portfolio, symbol, last_close[symbol], last_close) > 0:
                        queue.append(("TRIM", symbol))

        # --- (d) Record the portfolio at today's close ---
        total = pf.get_total_value(portfolio, last_close)
        holdings_value = total - portfolio["cash"]
        biggest = 0.0
        for symbol in portfolio["holdings"]:
            weight = pf.get_position_value(portfolio, symbol, last_close) / total * 100
            if weight > biggest:
                biggest = weight
        result_dates.append(date)
        equity_curve.append(total)
        cash_curve.append(portfolio["cash"])
        invested_curve.append(holdings_value / total * 100)
        positions_curve.append(len(portfolio["holdings"]))
        max_weight_curve.append(biggest)
    print(" done.")

    # ----- 4. Benchmark = buy SPY on day 1 with the same starting cash and hold -----
    benchmark_curve = []
    for close in bench_closes:
        benchmark_curve.append(start_cash * close / bench_closes[0])

    return {
        "dates": result_dates,
        "equity": equity_curve,
        "benchmark": benchmark_curve,
        "cash": cash_curve,
        "invested_pct": invested_curve,
        "positions": positions_curve,
        "max_weight": max_weight_curve,
        "trades": trades,
        "start_cash": start_cash,
        "final_portfolio": portfolio,
        "final_prices": last_close,
        "stocks_tested": list(stocks.keys()),
        "rejected": rejected,
        "settings": {"years": years, "check_every": check_every,
                     "use_fundamentals": use_fundamentals},
    }
