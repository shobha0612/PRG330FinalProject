# portfolio.py
# MODULE 5 - Stores what the user owns and calculates allocation percentages.
# Concepts used: dictionaries, file handling (JSON + CSV), os module, for loops
#
# The portfolio is ONE dictionary that looks like this:
# {
#   "cash": 95000.0,
#   "holdings": {"AAPL": {"shares": 20, "avg_price": 190.5, "sector": "Technology"}},
#   "pending_orders": []
# }
# It is saved to data/portfolio.json, which acts as our simple database.

import json
import csv
import os
import config


def new_portfolio():
    """Creates a brand-new portfolio with the starting cash."""
    return {"cash": config.STARTING_CASH, "holdings": {}, "pending_orders": []}


def load_portfolio():
    """Reads the portfolio file. If it does not exist yet, starts a new one."""
    if os.path.exists(config.PORTFOLIO_FILE):
        with open(config.PORTFOLIO_FILE, "r") as file:
            return json.load(file)
    return new_portfolio()


def save_portfolio(portfolio):
    """Writes the portfolio dictionary to the JSON file."""
    folder = os.path.dirname(config.PORTFOLIO_FILE)
    if folder != "" and not os.path.exists(folder):
        os.makedirs(folder)
    with open(config.PORTFOLIO_FILE, "w") as file:
        json.dump(portfolio, file, indent=4)


def get_position_value(portfolio, symbol, prices):
    """Market value of one holding (shares x current price)."""
    if symbol not in portfolio["holdings"]:
        return 0.0
    holding = portfolio["holdings"][symbol]
    price = prices.get(symbol, holding["avg_price"])    # fall back to buy price
    return holding["shares"] * price


def get_holdings_value(portfolio, prices):
    """Market value of ALL stocks owned."""
    total = 0.0
    for symbol in portfolio["holdings"]:
        total = total + get_position_value(portfolio, symbol, prices)
    return total


def get_total_value(portfolio, prices):
    """Total portfolio value = cash + all holdings."""
    return portfolio["cash"] + get_holdings_value(portfolio, prices)


def get_allocation_percent(portfolio, symbol, prices):
    """What % of the whole portfolio is in this stock?"""
    total = get_total_value(portfolio, prices)
    if total <= 0:
        return 0.0
    return get_position_value(portfolio, symbol, prices) / total * 100


def print_portfolio(portfolio, prices):
    """Prints a table of holdings with allocation and a High Concentration flag."""
    total = get_total_value(portfolio, prices)
    print("\n================ PORTFOLIO ================")
    print("Cash:            $" + format(portfolio["cash"], ",.2f"))
    print("Stocks value:    $" + format(get_holdings_value(portfolio, prices), ",.2f"))
    print("TOTAL VALUE:     $" + format(total, ",.2f"))

    if len(portfolio["holdings"]) == 0:
        print("(no holdings yet)")
        return

    print("\n{:<7}{:>8}{:>11}{:>11}{:>13}{:>9}  {}".format(
        "Symbol", "Shares", "Avg Cost", "Price", "Value", "Alloc%", "Note"))
    for symbol in portfolio["holdings"]:
        holding = portfolio["holdings"][symbol]
        price = prices.get(symbol, holding["avg_price"])
        value = holding["shares"] * price
        percent = get_allocation_percent(portfolio, symbol, prices)
        note = ""
        if percent > config.MAX_POSITION_PERCENT:
            note = "HIGH CONCENTRATION"
        print("{:<7}{:>8}{:>11.2f}{:>11.2f}{:>13,.2f}{:>8.2f}%  {}".format(
            symbol, holding["shares"], holding["avg_price"], price, value, percent, note))


def export_allocation_csv(portfolio, prices):
    """Writes an allocation report to a CSV file (can be opened in Excel)."""
    folder = os.path.dirname(config.ALLOCATION_FILE)
    if folder != "" and not os.path.exists(folder):
        os.makedirs(folder)

    with open(config.ALLOCATION_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["symbol", "sector", "shares", "avg_price", "current_price",
                         "value", "allocation_percent", "high_concentration"])
        for symbol in portfolio["holdings"]:
            holding = portfolio["holdings"][symbol]
            price = prices.get(symbol, holding["avg_price"])
            percent = get_allocation_percent(portfolio, symbol, prices)
            flag = "YES" if percent > config.MAX_POSITION_PERCENT else "NO"
            writer.writerow([symbol, holding["sector"], holding["shares"],
                             round(holding["avg_price"], 2), round(price, 2),
                             round(holding["shares"] * price, 2), round(percent, 2), flag])
        writer.writerow(["CASH", "", "", "", "", round(portfolio["cash"], 2), "", ""])
