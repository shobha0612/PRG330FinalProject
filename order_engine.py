# order_engine.py
# MODULE 7 - Places simulated BUY/SELL orders, but only during trading hours.
# Concepts used: datetime, functions, if/else, lists, file handling (CSV append)
#
# Market open  -> order is filled immediately (simulated).
# Market closed -> order is put in a "pending_orders" list and filled when the market opens.

import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo        # on Windows run: pip install tzdata

import config
import portfolio as pf
import risk_manager


# ---------------------------------------------------------------------------
# Trading hours
# ---------------------------------------------------------------------------
def market_now():
    """Current date/time in New York (where the S&P 500 trades)."""
    return datetime.now(ZoneInfo(config.MARKET_TIMEZONE))


def is_market_open():
    """True on Mon-Fri between 9:30 and 16:00 New York time."""
    if config.IGNORE_MARKET_HOURS:
        return True
    now = market_now()
    if now.weekday() >= 5:               # 5 = Saturday, 6 = Sunday
        return False
    minutes_now = now.hour * 60 + now.minute
    opens = config.MARKET_OPEN_HOUR * 60 + config.MARKET_OPEN_MINUTE
    closes = config.MARKET_CLOSE_HOUR * 60 + config.MARKET_CLOSE_MINUTE
    return opens <= minutes_now < closes


def print_market_status():
    now = market_now()
    status = "OPEN" if is_market_open() else "CLOSED"
    note = "  (trading-hours check is OFF for testing)" if config.IGNORE_MARKET_HOURS else ""
    print("Market is " + status + " | New York time: " + now.strftime("%a %Y-%m-%d %H:%M") + note)
    print("(Holidays are not checked in this simple version.)")


# ---------------------------------------------------------------------------
# Trade log (CSV)
# ---------------------------------------------------------------------------
def log_trade(side, symbol, qty, price, note=""):
    """Appends one line to data/trades.csv (creates the file with a header if new)."""
    folder = os.path.dirname(config.TRADES_FILE)
    if folder != "" and not os.path.exists(folder):
        os.makedirs(folder)
    is_new_file = not os.path.exists(config.TRADES_FILE)

    with open(config.TRADES_FILE, "a", newline="") as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow(["time", "side", "symbol", "quantity", "price", "total", "note"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), side, symbol, qty,
                         round(price, 2), round(qty * price, 2), note])


def print_trade_history():
    if not os.path.exists(config.TRADES_FILE):
        print("No trades yet.")
        return
    print("\n================ TRADE HISTORY ================")
    with open(config.TRADES_FILE, "r") as file:
        reader = csv.reader(file)
        for row in reader:
            print("{:<20}{:<6}{:<7}{:>6}{:>10}{:>12}  {}".format(*row))


# ---------------------------------------------------------------------------
# Executing orders
# ---------------------------------------------------------------------------
def execute_buy(portfolio, symbol, qty, price, sector, note=""):
    cost = qty * price
    if qty <= 0 or cost > portfolio["cash"]:
        return False

    holdings = portfolio["holdings"]
    if symbol in holdings:
        old = holdings[symbol]
        new_shares = old["shares"] + qty
        old["avg_price"] = (old["shares"] * old["avg_price"] + cost) / new_shares
        old["shares"] = new_shares
    else:
        holdings[symbol] = {"shares": qty, "avg_price": price, "sector": sector}

    portfolio["cash"] = portfolio["cash"] - cost
    log_trade("BUY", symbol, qty, price, note)
    return True


def execute_sell(portfolio, symbol, qty, price, note=""):
    holdings = portfolio["holdings"]
    if symbol not in holdings or qty <= 0:
        return False
    qty = min(qty, holdings[symbol]["shares"])       # cannot sell more than we own

    profit = (price - holdings[symbol]["avg_price"]) * qty
    portfolio["cash"] = portfolio["cash"] + qty * price
    holdings[symbol]["shares"] = holdings[symbol]["shares"] - qty
    if holdings[symbol]["shares"] == 0:
        del holdings[symbol]

    log_trade("SELL", symbol, qty, price, note + " P/L=" + str(round(profit, 2)))
    return True


def place_order(portfolio, side, symbol, qty, price, sector, mode, note="", ignore_hours=False):
    """
    The single entry point for every order.
    Returns "FILLED", "QUEUED" or "REJECTED".
    ignore_hours=True is used for STARTER holdings, which are set up at any time.
    """
    if not ignore_hours and not is_market_open():
        portfolio["pending_orders"].append({
            "side": side, "symbol": symbol, "qty": qty, "price": price,
            "sector": sector, "mode": mode, "note": note})
        return "QUEUED"

    if side == "BUY":
        done = execute_buy(portfolio, symbol, qty, price, sector, note)
    else:
        done = execute_sell(portfolio, symbol, qty, price, note)

    if done:
        return "FILLED"
    return "REJECTED"


def process_pending_orders(portfolio, prices):
    """Runs queued orders once the market is open, using fresh prices and the 5% rule."""
    if len(portfolio["pending_orders"]) == 0:
        print("No pending orders.")
        return
    if not is_market_open():
        print("Market is closed - pending orders keep waiting.")
        return

    for order in portfolio["pending_orders"]:
        symbol = order["symbol"]
        price = prices.get(symbol, order["price"])

        if order["side"] == "BUY":
            qty, messages, warning = risk_manager.validate_buy(
                portfolio, symbol, order["qty"], price, prices, order["mode"])
            if qty > 0 and execute_buy(portfolio, symbol, qty, price, order["sector"],
                                       order["note"] + " (was queued)"):
                print("Filled queued BUY", qty, symbol, "@", round(price, 2))
            else:
                print("Dropped queued BUY", symbol, "-", " ".join(messages))
        else:
            if execute_sell(portfolio, symbol, order["qty"], price, order["note"] + " (was queued)"):
                print("Filled queued SELL", order["qty"], symbol, "@", round(price, 2))
            else:
                print("Dropped queued SELL", symbol)

    portfolio["pending_orders"] = []        # every queued order has now been handled
