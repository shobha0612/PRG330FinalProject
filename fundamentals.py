# fundamentals.py
# MODULE 3 - Judges the BUSINESS (not the price chart).
# Concepts used: dictionaries, lists of tuples, if/elif/else, for loops, functions
#
# Idea: different industries are judged by different rules.
#   * Free cash flow matters for factories, retailers, energy companies.
#   * It matters LESS for tech firms that reinvest heavily (data centres, R&D),
#     so for them we look at ROCE, growth, margins and low debt instead.
#   * Banks live on debt, so debt ratios make no sense for them: we use P/B and ROE.
#
# Each rule is a tuple:  (metric_name, ">" or "<", limit, description)

import config

TECH_RULES = [
    ("revenue_growth",      ">", 0.10, "Revenue growth > 10%"),
    ("revenue_consistency", ">", 0.65, "Revenue grew in most recent years (customer stickiness)"),
    ("gross_margin",        ">", 0.50, "Gross margin > 50% (pricing power)"),
    ("operating_margin",    ">", 0.15, "Operating margin > 15%"),
    ("roce",                ">", 0.12, "ROCE > 12% (heavy capex must earn a return)"),
    ("debt_to_equity",      "<", 1.0,  "Debt/Equity < 1.0"),
    ("peg",                 "<", 2.5,  "PEG (P/E to growth) < 2.5"),
    ("current_ratio",       ">", 1.0,  "Current ratio > 1.0"),
]

HEALTHCARE_RULES = [
    ("revenue_growth",   ">", 0.05, "Revenue growth > 5%"),
    ("gross_margin",     ">", 0.40, "Gross margin > 40%"),
    ("operating_margin", ">", 0.10, "Operating margin > 10%"),
    ("roe",              ">", 0.10, "ROE > 10%"),
    ("debt_to_equity",   "<", 1.0,  "Debt/Equity < 1.0"),
    ("current_ratio",    ">", 1.2,  "Current ratio > 1.2"),
    ("pe",               "<", 35,   "P/E < 35"),
]

FINANCIAL_RULES = [   # banks, insurers: debt/FCF are not meaningful
    ("pbv",           "<", 3.0,  "Price/Book < 3"),
    ("roe",           ">", 0.10, "ROE > 10%"),
    ("pe",            "<", 20,   "P/E < 20"),
    ("profit_margin", ">", 0.15, "Net profit margin > 15%"),
    ("revenue_growth", ">", 0.0, "Revenue is growing"),
    ("roa",           ">", 0.008, "ROA > 0.8%"),
]

HEAVY_INDUSTRY_RULES = [   # industrials, energy, materials: factories, pipelines, mines
    ("free_cashflow",     ">", 0,    "Free cash flow is positive"),
    ("net_debt_to_ebitda", "<", 3.0, "Net debt / EBITDA < 3"),
    ("roce",              ">", 0.08, "ROCE > 8%"),
    ("operating_margin",  ">", 0.08, "Operating margin > 8%"),
    ("pbv",               "<", 4.0,  "Price/Book < 4"),
    ("pe",                "<", 25,   "P/E < 25"),
    ("current_ratio",     ">", 1.0,  "Current ratio > 1.0"),
    ("debt_to_equity",    "<", 1.5,  "Debt/Equity < 1.5"),
]

CONSUMER_STAPLES_RULES = [   # retail, food, household goods: steady, sticky customers
    ("free_cashflow",       ">", 0,    "Free cash flow is positive"),
    ("fcf_margin",          ">", 0.03, "FCF margin > 3%"),
    ("profit_margin",       ">", 0.04, "Net profit margin > 4%"),
    ("gross_margin",        ">", 0.25, "Gross margin > 25%"),
    ("roe",                 ">", 0.12, "ROE > 12%"),
    ("debt_to_equity",      "<", 1.5,  "Debt/Equity < 1.5"),
    ("revenue_consistency", ">", 0.65, "Sales grew in most recent years (stickiness)"),
    ("pe",                  "<", 30,   "P/E < 30"),
]

CONSUMER_CYCLICAL_RULES = [
    ("free_cashflow",    ">", 0,    "Free cash flow is positive"),
    ("revenue_growth",   ">", 0.03, "Revenue growth > 3%"),
    ("operating_margin", ">", 0.08, "Operating margin > 8%"),
    ("roe",              ">", 0.12, "ROE > 12%"),
    ("debt_to_equity",   "<", 1.5,  "Debt/Equity < 1.5"),
    ("pe",               "<", 30,   "P/E < 30"),
    ("peg",              "<", 2.5,  "PEG < 2.5"),
]

UTILITIES_RULES = [   # always carry lots of debt, steady dividends
    ("debt_to_equity",   "<", 2.0,  "Debt/Equity < 2.0 (utilities borrow a lot)"),
    ("profit_margin",    ">", 0.08, "Net profit margin > 8%"),
    ("operating_margin", ">", 0.12, "Operating margin > 12%"),
    ("pe",               "<", 25,   "P/E < 25"),
    ("pbv",              "<", 3.0,  "Price/Book < 3"),
    ("dividend_rate",    ">", 0,    "Pays a dividend"),
]

REAL_ESTATE_RULES = [
    ("debt_to_equity",   "<", 2.0,  "Debt/Equity < 2.0"),
    ("operating_margin", ">", 0.20, "Operating margin > 20%"),
    ("dividend_rate",    ">", 0,    "Pays a dividend"),
    ("pbv",              "<", 3.0,  "Price/Book < 3"),
    ("revenue_growth",   ">", 0.0,  "Revenue is growing"),
]

COMMUNICATION_RULES = [
    ("revenue_growth",   ">", 0.03, "Revenue growth > 3%"),
    ("operating_margin", ">", 0.12, "Operating margin > 12%"),
    ("roce",             ">", 0.08, "ROCE > 8%"),
    ("debt_to_equity",   "<", 1.5,  "Debt/Equity < 1.5"),
    ("free_cashflow",    ">", 0,    "Free cash flow is positive"),
    ("pe",               "<", 30,   "P/E < 30"),
]

DEFAULT_RULES = [   # used when the sector is unknown
    ("profit_margin",  ">", 0.05, "Net profit margin > 5%"),
    ("roe",            ">", 0.10, "ROE > 10%"),
    ("debt_to_equity", "<", 1.5,  "Debt/Equity < 1.5"),
    ("pe",             "<", 30,   "P/E < 30"),
    ("current_ratio",  ">", 1.0,  "Current ratio > 1.0"),
    ("revenue_growth", ">", 0.0,  "Revenue is growing"),
]

# Sector names are the ones Yahoo Finance uses
SECTOR_RULES = {
    "Technology": TECH_RULES,
    "Healthcare": HEALTHCARE_RULES,
    "Financial Services": FINANCIAL_RULES,
    "Industrials": HEAVY_INDUSTRY_RULES,
    "Energy": HEAVY_INDUSTRY_RULES,
    "Basic Materials": HEAVY_INDUSTRY_RULES,
    "Consumer Defensive": CONSUMER_STAPLES_RULES,
    "Consumer Cyclical": CONSUMER_CYCLICAL_RULES,
    "Utilities": UTILITIES_RULES,
    "Real Estate": REAL_ESTATE_RULES,
    "Communication Services": COMMUNICATION_RULES,
}


def calculate_metrics(raw):
    """
    Turns the raw API numbers into the ratios our rules use.
    Anything that cannot be calculated stays None.
    """
    m = {}

    # Ratios Yahoo already gives us
    for key in ["pe", "forward_pe", "pbv", "ps", "eps", "roe", "roa",
                "gross_margin", "operating_margin", "profit_margin",
                "revenue_growth", "earnings_growth", "current_ratio",
                "quick_ratio", "free_cashflow", "dividend_rate"]:
        m[key] = raw.get(key)

    # Yahoo reports Debt/Equity in percent (150 means 1.5), so divide by 100
    debt_equity = raw.get("debt_to_equity")
    if debt_equity is not None:
        m["debt_to_equity"] = debt_equity / 100
    else:
        m["debt_to_equity"] = None

    # PEG = P/E divided by earnings growth in percent (use Yahoo's value if present)
    m["peg"] = raw.get("peg")
    if m["peg"] is None and raw.get("pe") and raw.get("earnings_growth"):
        if raw["pe"] > 0 and raw["earnings_growth"] > 0:
            m["peg"] = raw["pe"] / (raw["earnings_growth"] * 100)

    # ROCE = EBIT / (Total Assets - Current Liabilities)
    m["roce"] = None
    ebit = raw.get("ebit")
    assets = raw.get("total_assets")
    liabilities = raw.get("current_liabilities")
    if ebit is not None and assets is not None and liabilities is not None:
        capital_employed = assets - liabilities
        if capital_employed > 0:
            m["roce"] = ebit / capital_employed

    # Capital expenditure as a share of revenue (shown in the report, not a pass/fail rule)
    m["capex_to_revenue"] = None
    revenue = raw.get("total_revenue")
    capex = raw.get("capex")
    if capex is not None and revenue:
        m["capex_to_revenue"] = abs(capex) / revenue

    # Free-cash-flow margin
    m["fcf_margin"] = None
    if raw.get("free_cashflow") is not None and revenue:
        m["fcf_margin"] = raw["free_cashflow"] / revenue

    # Net debt / EBITDA
    m["net_debt_to_ebitda"] = None
    ebitda = raw.get("ebitda")
    if ebitda and ebitda > 0 and raw.get("total_debt") is not None:
        cash = raw.get("total_cash")
        if cash is None:
            cash = 0
        m["net_debt_to_ebitda"] = (raw["total_debt"] - cash) / ebitda

    # Revenue consistency = share of recent years in which revenue went UP.
    # (Our simple stand-in for "customer stickiness".)
    m["revenue_consistency"] = None
    history = raw.get("revenue_history", [])      # newest year first
    pairs = len(history) - 1
    if pairs >= 2:
        growth_years = 0
        for i in range(pairs):
            if history[i] > history[i + 1]:
                growth_years = growth_years + 1
        m["revenue_consistency"] = growth_years / pairs

    return m


def analyze_fundamentals(raw):
    """
    Runs the sector's rules and returns a result dictionary:
        passed (True/False), sector, score_percent, details, metrics, reason
    """
    sector = raw.get("sector")
    rules = SECTOR_RULES.get(sector, DEFAULT_RULES)
    metrics = calculate_metrics(raw)

    result = {
        "sector": sector if sector else "Unknown",
        "metrics": metrics,
        "details": [],          # one line per rule: (description, value, True/False)
        "passed_rules": 0,
        "checked_rules": 0,
        "score_percent": 0,
        "passed": False,
        "reason": "",
    }

    # HARD RULE: a company losing money per share is rejected straight away
    eps = metrics.get("eps")
    if eps is not None and eps <= 0:
        result["reason"] = "Negative earnings (EPS <= 0)"
        return result

    # Check every rule of the sector
    for rule in rules:
        metric_name, operator, limit, description = rule
        value = metrics.get(metric_name)
        if value is None:
            continue                      # no data -> skip this rule

        if operator == ">":
            ok = value > limit
        else:
            ok = value < limit

        result["checked_rules"] = result["checked_rules"] + 1
        if ok:
            result["passed_rules"] = result["passed_rules"] + 1
        result["details"].append((description, value, ok))

    # Final verdict
    if result["checked_rules"] < config.MIN_RULES_REQUIRED:
        result["reason"] = "Not enough data to judge this company"
        return result

    result["score_percent"] = result["passed_rules"] / result["checked_rules"] * 100
    if result["score_percent"] >= config.FUNDAMENTAL_PASS_PERCENT:
        result["passed"] = True
        result["reason"] = "Strong fundamentals for its sector"
    else:
        result["reason"] = "Weak fundamentals for its sector"
    return result


def print_fundamental_report(raw, result):
    """Prints a readable report."""
    print("\n--- FUNDAMENTALS: " + str(raw.get("name")) + " (" + raw["symbol"] + ") ---")
    print("Sector:", result["sector"], "| Industry:", raw.get("industry"))

    m = result["metrics"]
    print("Valuation  -> P/E:", fmt(m["pe"]), "| P/B:", fmt(m["pbv"]),
          "| PEG:", fmt(m["peg"]), "| P/S:", fmt(m["ps"]), "| EPS:", fmt(m["eps"]))
    print("Returns    -> ROE:", pct(m["roe"]), "| ROCE:", pct(m["roce"]),
          "| Capex/Revenue:", pct(m["capex_to_revenue"]))

    print("Rules checked for this sector:")
    for description, value, ok in result["details"]:
        mark = "[PASS]" if ok else "[FAIL]"
        print("  " + mark, description, "(actual:", fmt(value) + ")")

    print("Score:", result["passed_rules"], "/", result["checked_rules"],
          "=", round(result["score_percent"]), "%")
    if result["passed"]:
        print("VERDICT: PASS -", result["reason"])
    else:
        print("VERDICT: REJECTED -", result["reason"])


def fmt(value):
    """Formats a number nicely, or 'n/a' if missing."""
    if value is None:
        return "n/a"
    return str(round(value, 2))


def pct(value):
    if value is None:
        return "n/a"
    return str(round(value * 100, 1)) + "%"
