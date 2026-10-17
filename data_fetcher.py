# data_fetcher.py
# MODULE 2 - The ONLY file that talks to the internet (the free yfinance API).
# Concepts used: functions, dictionaries, lists, try/except, for loops, file handling
#
# yfinance returns "pandas tables". To keep the rest of the project simple,
# we convert everything into plain Python lists and dictionaries right here.
#
# Two kinds of saving:
#   * MEMORY cache : remembers data for a few minutes during one run (expires, so the
#                    auto-trader never works with old prices).
#   * DISK cache   : saves data to data/cache/ so the BACKTEST DEMO works with NO internet.

import csv
import json
import os
import time

import config

try:
    import yfinance as yf
except ImportError:
    yf = None

# symbol -> (time saved, data)
price_cache = {}
fundamental_cache = {}


def check_api_ready():
    """Stops the program with a helpful message if yfinance is not installed."""
    if yf is None:
        print("yfinance is not installed. Run:  pip install yfinance")
        return False
    return True


# ---------------------------------------------------------------------------
# Disk cache helpers (CSV for prices, JSON for fundamentals)
# ---------------------------------------------------------------------------
def _history_path(symbol):
    return os.path.join(config.CACHE_FOLDER, symbol + "_prices.csv")


def _fundamental_path(symbol):
    return os.path.join(config.CACHE_FOLDER, symbol + "_fundamentals.json")


def _save_history_file(symbol, data):
    os.makedirs(config.CACHE_FOLDER, exist_ok=True)
    with open(_history_path(symbol), "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        for i in range(len(data["dates"])):
            writer.writerow([data["dates"][i], data["open"][i], data["high"][i],
                             data["low"][i], data["close"][i], data["volume"][i]])


def _load_history_file(symbol):
    path = _history_path(symbol)
    if not os.path.exists(path):
        return None
    data = {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    with open(path, "r") as file:
        reader = csv.reader(file)
        next(reader)                                   # skip the header row
        for row in reader:
            data["dates"].append(row[0])
            data["open"].append(float(row[1]))
            data["high"].append(float(row[2]))
            data["low"].append(float(row[3]))
            data["close"].append(float(row[4]))
            data["volume"].append(float(row[5]))
    if len(data["dates"]) < 60:
        return None
    return data


def _save_fundamental_file(symbol, data):
    os.makedirs(config.CACHE_FOLDER, exist_ok=True)
    with open(_fundamental_path(symbol), "w") as file:
        json.dump(data, file)


def _load_fundamental_file(symbol):
    path = _fundamental_path(symbol)
    if not os.path.exists(path):
        return None
    with open(path, "r") as file:
        return json.load(file)


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
def _download_history(symbol):
    """Downloads the full daily history from the API. Returns None on failure."""
    if not check_api_ready():
        return None
    try:
        table = yf.Ticker(symbol).history(period="max")   # "max" = since the stock was listed
    except Exception as error:
        print("Could not download prices for", symbol, "->", error)
        return None

    if table is None or len(table) < 60:
        print("Not enough price history for", symbol)
        return None

    dates = []
    for day in table.index:
        dates.append(day.strftime("%Y-%m-%d"))

    return {
        "dates": dates,
        "open": table["Open"].tolist(),
        "high": table["High"].tolist(),
        "low": table["Low"].tolist(),
        "close": table["Close"].tolist(),
        "volume": table["Volume"].tolist(),
    }


def get_price_history(symbol, use_disk_cache=False):
    """
    Returns the daily history of a stock (oldest -> newest) as a dictionary of lists:
        {"dates": [...], "open": [...], "high": [...], "low": [...],
         "close": [...], "volume": [...]}
    use_disk_cache=True : read data/cache/<symbol>_prices.csv if it exists (works offline),
                          otherwise download it and save it there.
    Returns None if nothing could be loaded.
    """
    # 1. memory (only if it is still fresh)
    saved = price_cache.get(symbol)
    if saved is not None and time.time() - saved[0] < config.PRICE_CACHE_SECONDS:
        return saved[1]

    # 2. disk
    if use_disk_cache:
        data = _load_history_file(symbol)
        if data is not None:
            price_cache[symbol] = (time.time(), data)
            return data

    # 3. internet
    data = _download_history(symbol)
    if data is not None:
        price_cache[symbol] = (time.time(), data)
        if use_disk_cache:
            _save_history_file(symbol, data)
    return data


def get_latest_price(symbol):
    """Returns the most recent price of a stock as a float (or None)."""
    if not check_api_ready():
        return None
    try:
        return float(yf.Ticker(symbol).fast_info["last_price"])
    except Exception:
        pass
    # Backup plan: use the last closing price of the last 5 days
    try:
        table = yf.Ticker(symbol).history(period="5d")
        return float(table["Close"].tolist()[-1])
    except Exception:
        return None


def get_current_prices(symbols):
    """Takes a list of tickers, returns {ticker: price}."""
    prices = {}
    for symbol in symbols:
        price = get_latest_price(symbol)
        if price is not None:
            prices[symbol] = price
    return prices


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------
def _row_values(table, names):
    """
    Financial statements from yfinance are tables: rows = line items
    (e.g. 'Total Revenue'), columns = years (newest first).
    This helper returns one row as a list of numbers, skipping empty (NaN) cells.
    """
    if table is None or table.empty:
        return []
    for name in names:
        if name in table.index:
            values = []
            for cell in table.loc[name].tolist():
                if cell == cell:            # a NaN is the only value not equal to itself
                    values.append(float(cell))
            return values
    return []


def _latest_value(table, names):
    values = _row_values(table, names)
    if len(values) == 0:
        return None
    return values[0]


def _download_fundamentals(symbol):
    """Collects raw company numbers into ONE flat dictionary (None = missing)."""
    if not check_api_ready():
        return None

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
    except Exception as error:
        print("Could not download fundamentals for", symbol, "->", error)
        return None

    if info is None or len(info) < 5:
        print("No fundamental data found for", symbol)
        return None

    data = {
        "symbol": symbol,
        "name": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        # --- valuation ---
        "pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pbv": info.get("priceToBook"),
        "peg": info.get("pegRatio") or info.get("trailingPegRatio"),
        "ps": info.get("priceToSalesTrailing12Months"),
        "eps": info.get("trailingEps"),
        # --- profitability ---
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "profit_margin": info.get("profitMargins"),
        # --- growth ---
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        # --- balance sheet / liquidity ---
        "debt_to_equity": info.get("debtToEquity"),     # Yahoo gives this in % (150 = 1.5x)
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "ebitda": info.get("ebitda"),
        # --- cash flow ---
        "free_cashflow": info.get("freeCashflow"),
        "operating_cashflow": info.get("operatingCashflow"),
        "total_revenue": info.get("totalRevenue"),
        "dividend_rate": info.get("dividendRate"),
    }

    # --- numbers that come from the financial statements ---
    try:
        income = ticker.financials
        balance = ticker.balance_sheet
        cashflow = ticker.cashflow
        data["ebit"] = _latest_value(income, ["EBIT", "Operating Income"])
        data["total_assets"] = _latest_value(balance, ["Total Assets"])
        data["current_liabilities"] = _latest_value(
            balance, ["Current Liabilities", "Total Current Liabilities"])
        data["capex"] = _latest_value(cashflow, ["Capital Expenditure"])
        data["revenue_history"] = _row_values(income, ["Total Revenue"])
    except Exception:
        data["ebit"] = None
        data["total_assets"] = None
        data["current_liabilities"] = None
        data["capex"] = None
        data["revenue_history"] = []

    time.sleep(0.5)               # be polite to the free API
    return data


def get_fundamental_data(symbol, use_disk_cache=False):
    """Same idea as get_price_history, but for company fundamentals."""
    saved = fundamental_cache.get(symbol)
    if saved is not None and time.time() - saved[0] < config.FUNDAMENTAL_CACHE_SECONDS:
        return saved[1]

    if use_disk_cache:
        data = _load_fundamental_file(symbol)
        if data is not None:
            fundamental_cache[symbol] = (time.time(), data)
            return data

    data = _download_fundamentals(symbol)
    if data is not None:
        fundamental_cache[symbol] = (time.time(), data)
        if use_disk_cache:
            _save_fundamental_file(symbol, data)
    return data


# ---------------------------------------------------------------------------
# Preparing the offline demo
# ---------------------------------------------------------------------------
def refresh_disk_cache(symbol, with_fundamentals=True):
    """
    Downloads FRESH data and saves it to data/cache/ (overwrites old files).
    Run this at home with internet; the backtest can then run in class offline.
    """
    history = _download_history(symbol)
    if history is None:
        return False
    _save_history_file(symbol, history)
    price_cache[symbol] = (time.time(), history)

    if with_fundamentals:
        raw = _download_fundamentals(symbol)
        if raw is not None:
            _save_fundamental_file(symbol, raw)
            fundamental_cache[symbol] = (time.time(), raw)
    return True
