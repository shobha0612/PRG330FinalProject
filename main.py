# main.py
# The program you run:   python main.py
# It imports our modules and connects them through a simple text menu.
# Concepts used: while loop (menu = "do-while"), input(), if/elif, functions, file reading

import os
import time

import config
import data_fetcher
import portfolio as pf
import risk_manager
import order_engine
import strategy
import backtester
import analytics
import fundamentals

try:
    import pandas_tools
    import numpy_stats
    import charts
except ImportError:
    pandas_tools = None
    numpy_stats = None
    charts = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def load_watchlist():
    """Reads watchlist.txt (one ticker per line, lines starting with # are comments)."""
    symbols = []
    try:
        with open(config.WATCHLIST_FILE, "r") as file:
            for line in file:
                line = line.strip().upper()
                if line != "" and not line.startswith("#"):
                    symbols.append(line)
    except FileNotFoundError:
        print("watchlist.txt not found.")
    return symbols


def get_holding_prices(portfolio):
    """Latest price of every stock we own."""
    return data_fetcher.get_current_prices(list(portfolio["holdings"].keys()))


def save_everything(portfolio, prices):
    pf.save_portfolio(portfolio)
    pf.export_allocation_csv(portfolio, prices)


def ask_number(question, default, kind):
    """Asks for a number. Pressing Enter keeps the default."""
    text = input(question + " [" + str(default) + "]: ").strip()
    if text == "":
        return default
    try:
        return kind(text)
    except ValueError:
        print("Not a valid number, using", default)
        return default


def ask_yes_no(question, default_yes):
    hint = "Y/n" if default_yes else "y/N"
    text = input(question + " (" + hint + "): ").strip().lower()
    if text == "":
        return default_yes
    return text.startswith("y")


# ---------------------------------------------------------------------------
# Menu actions - live portfolio
# ---------------------------------------------------------------------------
def show_portfolio(portfolio):
    prices = get_holding_prices(portfolio)
    pf.print_portfolio(portfolio, prices)
    if len(portfolio["pending_orders"]) > 0:
        print("\nPending orders waiting for market open:")
        for order in portfolio["pending_orders"]:
            print("  ", order["side"], order["qty"], order["symbol"])
    if len(portfolio["holdings"]) == 0:
        print("\nTip: your portfolio is empty. Use option 9 or 10 to add starter shares,")
        print("or option 11 to run a backtest on historical data.")
    save_everything(portfolio, prices)


def analyze_one_stock():
    symbol = input("Ticker to analyze (e.g. AAPL): ").strip().upper()
    if symbol == "":
        return
    print("Downloading data... (can take a few seconds)")
    result = strategy.evaluate_stock(symbol)
    if result is None:
        print("Could not analyze", symbol)
        return
    strategy.print_full_report(result)


def manual_buy(portfolio, starter=False):
    """
    Manual BUY. With starter=True the order is filled immediately even when the
    market is closed (used to set up the first shares of a portfolio).
    """
    symbol = input("Ticker to BUY: ").strip().upper()
    quantity_text = input("Quantity: ").strip()
    if symbol == "" or not quantity_text.isdigit() or int(quantity_text) <= 0:
        print("Please enter a ticker and a whole number quantity.")
        return
    quantity = int(quantity_text)

    print("Checking the company's fundamentals first...")
    result = strategy.evaluate_stock(symbol)
    if result is None:
        print("Could not get data for", symbol)
        return

    # Weak businesses can NEVER be bought, not even manually
    if result["action"] == "REJECT":
        print("ORDER BLOCKED:", symbol, "-", result["why"])
        return
    print("Fundamentals OK. Technical view:", result["tech"]["signal"],
          "(score " + str(result["tech"]["score"]) + ")")

    price = result["price"]
    prices = get_holding_prices(portfolio)
    prices[symbol] = price

    approved, messages, high_concentration = risk_manager.validate_buy(
        portfolio, symbol, quantity, price, prices, "manual")
    for line in messages:
        print(line)
    if approved <= 0:
        return

    if high_concentration:
        answer = input("Type YES to place this high-concentration order anyway: ")
        if answer.strip().upper() != "YES":
            print("Order cancelled.")
            return

    note = "starter holding" if starter else "manual"
    status = order_engine.place_order(portfolio, "BUY", symbol, approved, price,
                                      result["sector"], "manual", note, ignore_hours=starter)
    print("Order status:", status, "-", approved, symbol, "@", round(price, 2))
    save_everything(portfolio, prices)


def manual_sell(portfolio):
    symbol = input("Ticker to SELL: ").strip().upper()
    if symbol not in portfolio["holdings"]:
        print("You do not own", symbol)
        return
    owned = portfolio["holdings"][symbol]["shares"]
    quantity_text = input("Quantity (you own " + str(owned) + "): ").strip()
    if not quantity_text.isdigit() or int(quantity_text) <= 0:
        print("Please enter a whole number quantity.")
        return

    price = data_fetcher.get_latest_price(symbol)
    if price is None:
        print("Could not get a price for", symbol)
        return

    status = order_engine.place_order(portfolio, "SELL", symbol, int(quantity_text), price,
                                      portfolio["holdings"][symbol]["sector"], "manual", "manual")
    print("Order status:", status)
    prices = get_holding_prices(portfolio)
    save_everything(portfolio, prices)


def build_starter_portfolio(portfolio):
    """
    Builds a first portfolio automatically from the watchlist, at ANY time of day:
      * stocks with weak fundamentals are skipped
      * stocks with a bearish chart are skipped
      * each stock gets STARTER_ALLOCATION_PERCENT (4%) - safely under the 5% cap
    """
    print("\nBuilding a starter portfolio from", config.WATCHLIST_FILE, "...")
    print("Each stock gets about", config.STARTER_ALLOCATION_PERCENT, "% of the portfolio, at most",
          config.STARTER_MAX_STOCKS, "stocks.")
    prices = get_holding_prices(portfolio)
    bought = 0

    for symbol in load_watchlist():
        if bought >= config.STARTER_MAX_STOCKS:
            break
        if symbol in portfolio["holdings"]:
            continue

        result = strategy.evaluate_stock(symbol)
        time.sleep(config.SECONDS_BETWEEN_STOCKS)
        if result is None:
            print("{:<6} skipped (no data)".format(symbol))
            continue
        if result["action"] == "REJECT":
            print("{:<6} skipped - {}".format(symbol, result["why"]))
            continue
        if result["tech"]["signal"] == "SELL":
            print("{:<6} skipped - bearish chart right now".format(symbol))
            continue

        price = result["price"]
        prices[symbol] = price
        total = pf.get_total_value(portfolio, prices)
        wanted = int(total * config.STARTER_ALLOCATION_PERCENT / 100 // price)
        qty, messages, warning = risk_manager.validate_buy(
            portfolio, symbol, wanted, price, prices, "auto")
        if qty <= 0:
            print("{:<6} skipped - {}".format(symbol, " ".join(messages)))
            continue

        status = order_engine.place_order(portfolio, "BUY", symbol, qty, price,
                                          result["sector"], "auto", "starter holding",
                                          ignore_hours=True)
        print("{:<6} BOUGHT {} shares @ {} -> {}".format(symbol, qty, round(price, 2), status))
        bought = bought + 1

    save_everything(portfolio, prices)
    print("\nStarter portfolio ready:", bought, "stocks bought. Choose option 1 to view it.")


def reset_portfolio(portfolio):
    """Deletes all holdings and history and starts again with the starting cash."""
    answer = input("This deletes your portfolio and trade history. Type YES to continue: ")
    if answer.strip().upper() != "YES":
        print("Cancelled.")
        return
    for path in [config.PORTFOLIO_FILE, config.TRADES_FILE, config.ALLOCATION_FILE]:
        if os.path.exists(path):
            os.remove(path)
    fresh = pf.new_portfolio()
    portfolio["cash"] = fresh["cash"]
    portfolio["holdings"] = fresh["holdings"]
    portfolio["pending_orders"] = fresh["pending_orders"]
    pf.save_portfolio(portfolio)
    print("Portfolio reset. Cash: $" + format(portfolio["cash"], ",.2f"))


def run_pending(portfolio):
    prices = get_holding_prices(portfolio)
    for order in portfolio["pending_orders"]:
        if order["symbol"] not in prices:
            latest = data_fetcher.get_latest_price(order["symbol"])
            if latest is not None:
                prices[order["symbol"]] = latest
    order_engine.process_pending_orders(portfolio, prices)
    save_everything(portfolio, prices)


def auto_scan(portfolio):
    """One full scan: analyse every stock on the watchlist (and everything we own) and trade."""
    order_engine.print_market_status()
    symbols = load_watchlist()
    for symbol in portfolio["holdings"]:
        if symbol not in symbols:
            symbols.append(symbol)

    prices = get_holding_prices(portfolio)

    for symbol in symbols:
        owned = symbol in portfolio["holdings"]
        result = strategy.evaluate_stock(symbol, owned)
        time.sleep(config.SECONDS_BETWEEN_STOCKS)       # be polite to the free API
        if result is None:
            print("{:<6} skipped (no data)".format(symbol))
            continue

        price = result["price"]
        prices[symbol] = price
        print("{:<6} {:<8} {}".format(symbol, result["action"], result["why"]))

        if result["action"] == "BUY":
            wanted = risk_manager.max_shares_under_cap(portfolio, symbol, price, prices)
            if wanted <= 0:
                print("       already at the 5% cap - no more buying")
            else:
                qty, messages, warning = risk_manager.validate_buy(
                    portfolio, symbol, wanted, price, prices, "auto")
                for line in messages:
                    print("       " + line)
                if qty > 0:
                    status = order_engine.place_order(portfolio, "BUY", symbol, qty, price,
                                                      result["sector"], "auto", "auto-trader")
                    print("       AUTO BUY", qty, symbol, "@", round(price, 2), "->", status)

        elif result["action"] == "SELL" and owned:
            qty = portfolio["holdings"][symbol]["shares"]
            status = order_engine.place_order(portfolio, "SELL", symbol, qty, price,
                                              result["sector"], "auto", "auto-trader")
            print("       AUTO SELL", qty, symbol, "@", round(price, 2), "->", status)

        # A winner that grew past the 5% cap is trimmed back
        if owned and result["action"] != "SELL":
            excess = risk_manager.shares_to_trim(portfolio, symbol, price, prices)
            if excess > 0:
                status = order_engine.place_order(portfolio, "SELL", symbol, excess, price,
                                                  result["sector"], "auto", "trim to 5% cap")
                print("       AUTO TRIM", excess, symbol, "@", round(price, 2), "-> back to the 5% cap:", status)

    save_everything(portfolio, prices)
    print("\nScan finished.")


def auto_loop(portfolio):
    """Repeats the scan every few minutes while the market is open. Ctrl+C stops it."""
    print("Auto-trader started. Press Ctrl+C to stop.")
    try:
        while True:                                     # runs until we break out
            if order_engine.is_market_open():
                run_pending(portfolio)
                auto_scan(portfolio)
            else:
                order_engine.print_market_status()
                print("Waiting for the market to open...")
            print("Next scan in", config.AUTO_SCAN_MINUTES, "minutes.")
            time.sleep(config.AUTO_SCAN_MINUTES * 60)
    except KeyboardInterrupt:
        print("\nAuto-trader stopped.")


# ---------------------------------------------------------------------------
# Menu actions - backtest and statistics (work when the market is closed)
# ---------------------------------------------------------------------------
def prepare_demo_data():
    """Downloads everything once and saves it to data/cache so the demo works OFFLINE."""
    symbols = load_watchlist()
    print("Downloading and saving data for", len(symbols) + 1, "symbols to", config.CACHE_FOLDER)
    print("This takes a few minutes. Do it at home, with internet, before the class.")

    if data_fetcher.refresh_disk_cache(config.BENCHMARK_SYMBOL, False):
        print("{:<6} saved (benchmark)".format(config.BENCHMARK_SYMBOL))
    else:
        print("Benchmark download FAILED - the backtest cannot run without it.")
        return

    for symbol in symbols:
        if data_fetcher.refresh_disk_cache(symbol, True):
            print("{:<6} saved".format(symbol))
        else:
            print("{:<6} FAILED".format(symbol))
        time.sleep(config.SECONDS_BETWEEN_STOCKS)
    print("Done. You can now run option 11 (backtest) without internet.")


def run_backtest_menu():
    print("\n=== BACKTEST: replay history with the same rules (works any time) ===")
    symbols = load_watchlist()
    if len(symbols) == 0:
        return

    years = ask_number("Years to replay", config.BACKTEST_YEARS, float)
    cash = ask_number("Starting cash", config.STARTING_CASH, float)
    every = ask_number("Analyse stocks every N trading days", config.BACKTEST_CHECK_EVERY_DAYS, int)
    if years <= 0 or cash <= 0 or every <= 0:
        print("All values must be positive.")
        return
    use_fundamentals = ask_yes_no("Apply the fundamentals filter?", True)
    use_cache = ask_yes_no("Use saved data in data/cache if it exists (works offline)?", True)

    results = backtester.run_backtest(symbols, years, cash, every, use_fundamentals, use_cache)
    if results is None:
        return

    summary = analytics.print_report(results)
    print()
    analytics.export_csv_files(results)
    analytics.save_charts(results, summary)
    if ask_yes_no("\nCreate the full NumPy / pandas / matplotlib analysis?", True):
        if charts is None:
            library_message()
        else:
            charts.backtest_chart_pack(results)

    if ask_yes_no("\nShow every simulated trade?", False):
        print("\n{:<12}{:<6}{:<7}{:>6}{:>10}{:>12}".format("Date", "Side", "Symbol", "Qty", "Price", "P/L"))
        for t in results["trades"]:
            pnl_text = ""
            if t["side"] == "SELL":
                pnl_text = format(t["pnl"], "+,.0f")
            print("{:<12}{:<6}{:<7}{:>6}{:>10.2f}{:>12}".format(
                t["date"], t["side"], t["symbol"], t["qty"], t["price"], pnl_text))


def stock_statistics():
    symbol = input("Ticker to analyse (e.g. AAPL): ").strip().upper()
    if symbol == "":
        return
    years = ask_number("Years of history", 3, float)
    history = data_fetcher.get_price_history(symbol, True)
    benchmark = data_fetcher.get_price_history(config.BENCHMARK_SYMBOL, True)
    if history is None or benchmark is None:
        print("Could not load the data.")
        return
    analytics.print_stock_statistics(symbol, history, benchmark, years)


def library_message():
    """Prints the installation command when the optional library layer is unavailable."""
    print("This library option needs extra packages. Run: pip install numpy pandas matplotlib")


def stock_chart_dashboard():
    """Loads one cached history and draws its candlestick dashboard."""
    if charts is None:
        library_message()
        return
    symbol = input("Ticker for chart: ").strip().upper()
    history = data_fetcher.get_price_history(symbol, True)
    if history is None:
        print("Could not load saved history for", symbol)
        return
    plan = None
    try:
        import trade_plans
        plan = trade_plans.find_active_plan(symbol)
    except ImportError:
        pass
    print("Saved chart:", charts.candlestick_dashboard(symbol, history, config.CANDLE_DAYS, plan))


def watchlist_library_report():
    """Prints the pandas watchlist report and draws its portfolio analysis charts."""
    if charts is None:
        library_message()
        return
    symbols = load_watchlist()
    closes = pandas_tools.load_close_table(symbols, config.BACKTEST_YEARS, True)
    if closes.empty:
        print("No cached watchlist prices were found.")
        return
    stats = pandas_tools.watchlist_statistics(closes)
    print(stats)
    pandas_tools.save_table(stats, os.path.join(config.TABLE_FOLDER, "watchlist_statistics.csv"))
    result = numpy_stats.random_portfolios(closes, config.RANDOM_PORTFOLIOS)
    paths = [charts.frontier_chart(result, closes),
             charts.correlation_heatmap(pandas_tools.correlation_table(closes)),
             charts.normalised_prices_chart(closes, stats)]
    print("Gallery:", charts.write_gallery(paths, "Watchlist analysis"))


def portfolio_allocation_chart(portfolio):
    """Prints allocation data and draws the current portfolio allocation chart."""
    if charts is None:
        library_message()
        return
    prices = get_holding_prices(portfolio)
    if len(portfolio["holdings"]) == 0:
        print("Your portfolio is empty. Add starter shares before drawing an allocation chart.")
        return
    table, total = pandas_tools.portfolio_to_dataframe(portfolio, prices)
    print(table)
    pandas_tools.save_table(table, os.path.join(config.TABLE_FOLDER, "allocation.csv"))
    print("Saved chart:", charts.allocation_charts(portfolio, prices))


def fundamentals_library_charts():
    """Draws a fundamentals scorecard for one ticker and a peer chart for the watchlist."""
    if charts is None:
        library_message()
        return
    symbol = input("Ticker for fundamentals chart: ").strip().upper()
    raw = data_fetcher.get_fundamental_data(symbol, True)
    if raw is None:
        print("Could not load fundamentals for", symbol)
        return
    verdict = fundamentals.analyze_fundamentals(raw)
    table = pandas_tools.fundamentals_table(load_watchlist(), True)
    paths = [charts.fundamentals_scorecard(raw, verdict),
             charts.fundamentals_peer_chart(table)]
    print("Gallery:", charts.write_gallery(paths, "Fundamentals charts"))


def verify_library_calculations():
    """Prints comparisons between the plain-Python and library calculations."""
    if charts is None:
        library_message()
        return
    symbol = input("Ticker to verify: ").strip().upper()
    history = data_fetcher.get_price_history(symbol, True)
    if history is None:
        print("Could not load saved history for", symbol)
        return
    numpy_stats.print_verification(
        numpy_stats.verify_indicators(history), "Indicators: loops versus pandas")
    numpy_stats.print_verification(
        numpy_stats.verify_metrics(history["close"], history["dates"]),
        "Metrics: loops versus NumPy")


# ---------------------------------------------------------------------------
# Main menu (a while-True loop that ends with break = our "do-while")
# ---------------------------------------------------------------------------
def main():
    if not data_fetcher.check_api_ready():
        print("(Live features need yfinance. A backtest using saved data in data/cache still works.)")

    portfolio = pf.load_portfolio()
    print("=== Portfolio Management & Auto-Trading Simulator ===")
    print("(Educational simulation - virtual money only)")
    order_engine.print_market_status()

    while True:
        print("\n------------- MENU -------------")
        print(" LIVE SIMULATION (market hours)")
        print("  1. View portfolio")
        print("  2. Analyze a stock (fundamentals + technicals)")
        print("  3. Manual BUY")
        print("  4. Manual SELL")
        print("  5. Run auto-trader scan once")
        print("  6. Run auto-trader continuously")
        print("  7. Process pending orders")
        print("  8. Show trade history")
        print(" STARTER SHARES (work at any time)")
        print("  9. Add starter shares manually")
        print(" 10. Build a starter portfolio automatically from the watchlist")
        print(" 14. Reset portfolio")
        print(" BACKTEST & STATISTICS (work when the market is closed)")
        print(" 11. BACKTEST - replay history + full report")
        print(" 12. Statistics of one stock (descriptive + quantitative)")
        print(" 13. Prepare offline demo data (download once, run offline later)")
        print("  0. Exit")
        print(" LIBRARY ANALYSIS (NumPy / pandas / matplotlib)")
        print(" 20. Stock chart dashboard")
        print(" 21. Watchlist screener")
        print(" 22. Portfolio allocation chart")
        print(" 23. Fundamentals charts")
        print(" 24. Check: our loops versus NumPy / pandas")
        choice = input("Choose: ").strip()

        if choice == "1":
            show_portfolio(portfolio)
        elif choice == "2":
            analyze_one_stock()
        elif choice == "3":
            manual_buy(portfolio)
        elif choice == "4":
            manual_sell(portfolio)
        elif choice == "5":
            auto_scan(portfolio)
        elif choice == "6":
            auto_loop(portfolio)
        elif choice == "7":
            run_pending(portfolio)
        elif choice == "8":
            order_engine.print_trade_history()
        elif choice == "9":
            manual_buy(portfolio, starter=True)
        elif choice == "10":
            build_starter_portfolio(portfolio)
        elif choice == "11":
            run_backtest_menu()
        elif choice == "12":
            stock_statistics()
        elif choice == "13":
            prepare_demo_data()
        elif choice == "14":
            reset_portfolio(portfolio)
        elif choice == "20":
            stock_chart_dashboard()
        elif choice == "21":
            watchlist_library_report()
        elif choice == "22":
            portfolio_allocation_chart(portfolio)
        elif choice == "23":
            fundamentals_library_charts()
        elif choice == "24":
            verify_library_calculations()
        elif choice == "0":
            pf.save_portfolio(portfolio)
            print("Portfolio saved. Goodbye!")
            break
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    main()
