# strategy.py
# MODULE 8 - The "brain": runs the two-step filter and gives a final decision.
# Concepts used: functions, dictionaries, if/elif/else
#
#   STEP 1: Fundamentals  -> weak business?  REJECT (never buy it).
#   STEP 2: Technicals    -> is the chart favourable?  BUY / HOLD / SELL.

import data_fetcher
import fundamentals
import technicals


def evaluate_stock(symbol, owned=False):
    """
    Analyses one stock and returns a dictionary:
        symbol, price, sector, action, why, fund, tech, raw
    action is one of: "BUY", "SELL", "HOLD", "REJECT"
    Returns None if the data could not be downloaded.
    """
    # ----- STEP 1: fundamentals -----
    raw = data_fetcher.get_fundamental_data(symbol)
    if raw is None:
        return None
    fund = fundamentals.analyze_fundamentals(raw)

    result = {"symbol": symbol, "price": raw.get("price"), "sector": fund["sector"],
              "action": "HOLD", "why": "", "fund": fund, "tech": None, "raw": raw}

    if not fund["passed"]:
        if owned:
            result["action"] = "SELL"
            result["why"] = "Fundamentals turned weak (" + fund["reason"] + ") - exit position"
        else:
            result["action"] = "REJECT"
            result["why"] = fund["reason"] + " - not allowed to trade"
        return result

    # ----- STEP 2: technicals (only for stocks that passed step 1) -----
    history = data_fetcher.get_price_history(symbol)
    if history is None:
        return None
    tech = technicals.analyze_technicals(history)
    result["tech"] = tech
    result["price"] = tech["price"]

    if tech["signal"] == "BUY":
        result["action"] = "BUY"
        result["why"] = "Good business + bullish chart (score " + str(tech["score"]) + ")"
    elif tech["signal"] == "SELL":
        result["action"] = "SELL" if owned else "HOLD"
        result["why"] = "Good business but bearish chart (score " + str(tech["score"]) + ")"
    else:
        result["action"] = "HOLD"
        result["why"] = "Good business, chart not convincing (score " + str(tech["score"]) + ")"
    return result


def print_full_report(result):
    """Prints fundamentals, technicals and the final decision."""
    fundamentals.print_fundamental_report(result["raw"], result["fund"])
    if result["tech"] is not None:
        technicals.print_technical_report(result["symbol"], result["tech"])
    else:
        print("\n(Technical analysis skipped because the fundamentals filter failed.)")
    print("\n>>> FINAL DECISION for " + result["symbol"] + ": " + result["action"]
          + " - " + result["why"])
