# config.py
# MODULE 1 - All settings live here, so you never have to hunt through the code.
# Concepts used: variables, constants, numbers, strings, booleans

# ---------- Money ----------
STARTING_CASH = 100000.0          # virtual money a new user starts with

# ---------- Concentration rule ----------
MAX_POSITION_PERCENT = 5.0        # one stock may not exceed 5% of total portfolio value
ALLOW_MANUAL_OVERRIDE = True      # True  = manual orders may go above 5% (after a warning)
                                  # False = manual orders are also cut down to 5%
CASH_RESERVE_PERCENT = 10.0       # automatic orders always leave 10% of the portfolio in cash
REBALANCE_TOLERANCE_PERCENT = 1.0 # a winner is trimmed back to 5% once it grows past 5% + 1%

# ---------- Trading hours (US market, because we use S&P 500 stocks) ----------
MARKET_TIMEZONE = "America/New_York"
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
IGNORE_MARKET_HOURS = False       # set to True to test the simulator at night / weekends

# ---------- Files ----------
PORTFOLIO_FILE = "data/portfolio.json"     # our simple "database"
TRADES_FILE = "data/trades.csv"            # every order is logged here
ALLOCATION_FILE = "data/allocation.csv"    # allocation report (open in Excel)
WATCHLIST_FILE = "watchlist.txt"           # stocks the auto-trader looks at

# ---------- Auto trader ----------
AUTO_SCAN_MINUTES = 15            # how often the auto-trader repeats its scan
SECONDS_BETWEEN_STOCKS = 1        # small pause so the free API does not block us

# ---------- Fundamental filter ----------
FUNDAMENTAL_PASS_PERCENT = 60     # a stock must pass at least 60% of its sector rules
MIN_RULES_REQUIRED = 4            # and at least 4 rules must have data available

# ---------- Technical signal thresholds ----------
BUY_SCORE = 4                     # technical score >= 4  -> BUY
SELL_SCORE = -4                   # technical score <= -4 -> SELL

# ---------- Starter portfolio (for people who own no shares yet) ----------
STARTER_ALLOCATION_PERCENT = 4.0  # each starter stock gets 4% of the portfolio (under the 5% cap)
STARTER_MAX_STOCKS = 10           # buy at most 10 starter stocks

# ---------- Backtest (replays history, works even when the market is closed) ----------
BENCHMARK_SYMBOL = "SPY"          # S&P 500 ETF: our strategy is compared against it
BACKTEST_YEARS = 2                # how many years back to replay
BACKTEST_CHECK_EVERY_DAYS = 5     # analyse the stocks every 5 trading days (about weekly)
TRADING_COST_PERCENT = 0.05       # fee on every buy and sell, in % of the trade value
MIN_CANDLES_FOR_ANALYSIS = 260    # need about 1 year of past data before the first decision

# ---------- Statistics ----------
RISK_FREE_RATE = 0.04             # yearly rate used for Sharpe/Sortino/alpha (set to current T-bill rate)
TRADING_DAYS_PER_YEAR = 252

# ---------- Saved data (so the demo can run without internet) ----------
CACHE_FOLDER = "data/cache"
PRICE_CACHE_SECONDS = 600         # in a live session, prices older than 10 min are downloaded again
FUNDAMENTAL_CACHE_SECONDS = 21600 # fundamentals are refreshed every 6 hours

# ---------- Backtest output files ----------
BACKTEST_EQUITY_FILE = "data/backtest_equity.csv"
BACKTEST_TRADES_FILE = "data/backtest_trades.csv"
BACKTEST_CHART_FILE = "data/backtest_report.png"

# ---------- Library analysis layer ----------
CHART_FOLDER = "data/charts"
TABLE_FOLDER = "data/tables"
SHOW_CHARTS_ON_SCREEN = False
CHART_DPI = 120
MONTE_CARLO_PATHS = 2000
MONTE_CARLO_DAYS = 252
RANDOM_PORTFOLIOS = 4000
CANDLE_DAYS = 150
