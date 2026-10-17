# risk_manager.py
# MODULE 6 - Enforces the 5% single-stock cap.
# Concepts used: functions, if/elif/else, return of multiple values (tuples), math
#
# Two kinds of orders:
#   "auto"   -> strict. The quantity is automatically cut down so the stock stays <= 5%.
#   "manual" -> the user is in charge, so the order may exceed 5%, BUT the user gets a
#               "HIGH CONCENTRATION" warning (set ALLOW_MANUAL_OVERRIDE = False in
#               config.py to block manual orders above 5% as well).

import math

import config
import portfolio as pf


def max_position_value(total_value):
    """The most money allowed in ONE stock (5% of the total portfolio)."""
    return total_value * config.MAX_POSITION_PERCENT / 100


def max_shares_under_cap(portfolio, symbol, price, prices):
    """How many MORE shares can we buy before hitting the 5% cap?"""
    total = pf.get_total_value(portfolio, prices)
    room = max_position_value(total) - pf.get_position_value(portfolio, symbol, prices)
    if room <= 0 or price <= 0:
        return 0
    return int(room // price)          # whole shares only


def percent_after_buy(portfolio, symbol, qty, price, prices):
    """What would the stock's allocation be AFTER buying qty shares?"""
    total = pf.get_total_value(portfolio, prices)       # buying only swaps cash for stock
    new_value = pf.get_position_value(portfolio, symbol, prices) + qty * price
    return new_value / total * 100


def validate_buy(portfolio, symbol, qty, price, prices, mode):
    """
    Checks a BUY order. Returns three things:
        approved_qty        (how many shares we allow, can be 0)
        messages            (list of text lines to show the user)
        high_concentration  (True if the result is above the 5% cap)
    """
    messages = []
    total = pf.get_total_value(portfolio, prices)
    cap_qty = max_shares_under_cap(portfolio, symbol, price, prices)

    # How much cash may we spend?
    spendable = portfolio["cash"]
    if mode == "auto":
        reserve = total * config.CASH_RESERVE_PERCENT / 100
        spendable = spendable - reserve
    if spendable > 0:
        cash_qty = int(spendable // price)
    else:
        cash_qty = 0

    if cash_qty < qty:
        messages.append("Not enough spendable cash for " + str(qty) + " shares (max "
                        + str(cash_qty) + ").")

    # ----- AUTOMATIC orders: always obey the cap -----
    if mode == "auto":
        approved = min(qty, cap_qty, cash_qty)
        if approved < qty:
            messages.append("Auto order reduced from " + str(qty) + " to " + str(approved)
                            + " shares (5% cap / cash reserve).")
        if approved <= 0:
            messages.append("Auto order blocked.")
        return approved, messages, False

    # ----- MANUAL orders: user decides, but gets warned -----
    approved = min(qty, cash_qty)
    if approved <= 0:
        messages.append("Manual order blocked: no cash.")
        return 0, messages, False

    new_percent = percent_after_buy(portfolio, symbol, approved, price, prices)
    high_concentration = new_percent > config.MAX_POSITION_PERCENT

    if high_concentration:
        messages.append("*** HIGH CONCENTRATION WARNING ***")
        messages.append(symbol + " would be " + str(round(new_percent, 2)) + "% of your portfolio "
                        + "(limit is " + str(config.MAX_POSITION_PERCENT) + "%).")
        if not config.ALLOW_MANUAL_OVERRIDE:
            approved = cap_qty
            high_concentration = False
            messages.append("Manual override is OFF: order reduced to " + str(approved) + " shares.")
            if approved <= 0:
                messages.append("Manual order blocked.")
    return approved, messages, high_concentration


def shares_to_trim(portfolio, symbol, price, prices):
    """
    A winning stock can grow beyond 5% of the portfolio. Once it is more than
    REBALANCE_TOLERANCE_PERCENT above the cap, this returns how many shares to
    sell to bring it back to 5% (0 means: no trimming needed).
    """
    if symbol not in portfolio["holdings"] or price <= 0:
        return 0
    total = pf.get_total_value(portfolio, prices)
    if total <= 0:
        return 0
    value = pf.get_position_value(portfolio, symbol, prices)
    weight = value / total * 100
    if weight <= config.MAX_POSITION_PERCENT + config.REBALANCE_TOLERANCE_PERCENT:
        return 0
    excess_value = value - max_position_value(total)
    shares = int(math.ceil(excess_value / price))
    return min(shares, portfolio["holdings"][symbol]["shares"])
