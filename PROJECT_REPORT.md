# Portfolio Management and Auto-Trading Simulator

## Project Report

### 1. Introduction

This project is an educational portfolio-management and auto-trading simulator
written in Python. It uses virtual money only and is designed to demonstrate how
Python can be used to collect data, analyse companies, calculate indicators,
manage a portfolio, simulate trades, and present results through tables and
charts. It is not intended to provide financial advice or to place real
orders.

The project combines a command-line program, a Streamlit browser dashboard, and
a Jupyter Notebook version of the main program. The system can use free market
data from `yfinance`, but it also saves downloaded data in a local cache. This
means the main demonstration and backtest can run without an internet
connection, which is particularly useful in a classroom environment.

The main idea is a two-stage investment decision. First, a stock is checked
using fundamental information about the business. If it passes the
fundamental filter, its price history is checked using technical indicators.
The final decision is `BUY`, `HOLD`, `SELL`, or `REJECT`. Orders then pass
through risk-management and trading-hours rules before they are filled or
queued.

### 2. How the project works

The program is divided into small modules, with each module responsible for one
part of the application. This makes the code easier to understand, test, and
extend.

* `config.py` contains settings such as starting cash, the five-percent
  position limit, trading hours, benchmark symbol, fees, and chart options.
* `data_fetcher.py` downloads price and fundamental data and stores it in
  memory or in `data/cache/`. Cached data allows the offline demonstration and
  prevents the application from repeatedly requesting the same data.
* `fundamentals.py` evaluates business quality using sector-specific rules.
  Examples include profitability, growth, debt, liquidity, valuation, and
  return measures. A company must pass the configured percentage of available
  rules.
* `technicals.py` calculates indicators including simple and exponential moving
  averages, RSI, MACD, Bollinger Bands, stochastic values, OBV, price changes,
  and candle patterns. These values contribute to a technical score.
* `strategy.py` connects the two analyses. Weak businesses are rejected before
  technical analysis is used. A stock with good fundamentals but a bearish
  chart is not bought; an already-owned stock can be marked for sale.
* `portfolio.py` stores cash and holdings and calculates total value,
  position values, and allocation percentages. The portfolio is saved as JSON,
  while trades and allocations are also exported as CSV files.
* `risk_manager.py` applies the five-percent maximum position rule, maintains a
  cash reserve for automatic orders, warns about high concentration, and trims
  successful positions that grow beyond the limit.
* `order_engine.py` checks whether the US market is open. Orders placed while
  the market is closed are placed in a pending queue and processed when the
  market opens.
* `backtester.py` replays historical data one day at a time. It uses the same
  trading and risk rules as the live simulator, but it fills queued orders at
  the following day's open. This avoids using information from the future.
* `analytics.py` provides hand-written descriptive and quantitative statistics.
  `pandas_tools.py` and `numpy_stats.py` provide a library-based analysis layer
  for comparison and larger data operations.
* `charts.py` creates the visual reports, saves PNG files, and creates an HTML
  gallery linking to the generated charts.
* `main.py` provides the menu-driven command-line interface, while `app.py`
  provides the Streamlit dashboard.

The normal workflow begins with a watchlist of ticker symbols. A user can
inspect a company, build a starter portfolio, buy and sell manually, run an
automatic scan, replay a backtest, calculate stock statistics, or create
library-based charts. A typical starter portfolio allocates about four percent
to each selected stock, keeping it below the five-percent concentration cap.

### 3. Python concepts implemented from class

The project applies the Python concepts learned in class to a realistic
problem. Basic variables and constants are used in `config.py` so that
important settings are defined in one place. Strings, numbers, Boolean values,
lists, dictionaries, and tuples are used throughout the application to
represent prices, holdings, orders, rules, and results.

Functions are used extensively to divide the program into understandable
tasks. For example, `daily_returns`, `max_drawdown`, `evaluate_stock`,
`run_backtest`, and `candlestick_dashboard` each have one clear purpose.
Parameters and return values make these functions reusable and reduce
duplication.

Conditional statements control decisions such as whether a company passes its
fundamental rules, whether a signal is bullish or bearish, and whether an
order is allowed. `for` loops process watchlist symbols, historical dates,
trades, and chart series. The menu in `main.py` uses a `while True` loop with
`break`, which demonstrates how a command-line program can continue until the
user selects the exit option.

File handling is another important part of the project. The program reads
`watchlist.txt`, saves the portfolio to JSON, writes trade history and
allocation tables to CSV, and stores charts as PNG images. Exception handling
is used for missing files, unavailable data, and optional analysis libraries.
User input is validated before quantities, prices, and menu choices are used.

The project also demonstrates modular imports. Rather than placing every
operation in one large file, `main.py` imports the data, portfolio, strategy,
risk, order, backtesting, and analytics modules. This reflects a practical
Python project structure and makes individual components easier to test.

The hand-written calculations were kept deliberately. For example, the
functions for mean, median, standard deviation, covariance, correlation,
returns, Sharpe ratio, Sortino ratio, beta, alpha, and maximum drawdown use
lists, loops, and formulas that can be read directly. The library layer then
uses pandas for DataFrames and rolling calculations, NumPy for vectorised
calculations and simulations, and matplotlib for visualisation. Menu option 24
compares the two implementations and reports their differences. This shows
both how the formulas work and how professional Python libraries can make
analysis more efficient.

### 4. Main features and charts

#### Portfolio and trading features

The simulator starts with virtual cash and records every filled order. It
supports manual buying and selling, automatic watchlist scanning, pending
orders, starter portfolios, portfolio allocation, trade history, and CSV
exports. The risk rules are visible to the user: automatic buying is limited
to five percent per stock, manual orders can produce a high-concentration
warning, and winners are partially sold when they grow too far above the
limit.

#### Stock-analysis charts

The candlestick dashboard combines four related views. The first panel shows
open-high-low-close candles with SMA20, SMA50, SMA200, and the Bollinger Band
area. The second panel shows volume. The third panel shows RSI with the
traditional 30 and 70 reference levels. The fourth panel shows MACD, its
signal line, and the histogram. Together, these panels explain price direction,
market activity, momentum, and possible trend changes.

#### Backtest and risk charts

The equity dashboard compares the strategy value with an SPY buy-and-hold
benchmark. Buy and sell events are marked on the equity curve. Additional
panels show drawdown, rolling Sharpe ratio, and the percentage of the portfolio
that is invested. The monthly heatmap makes positive and negative months easy
to compare across years.

The return-distribution chart contains a histogram of daily returns, a
reference normal curve, a 95-percent Value at Risk marker, and a Q-Q plot.
The trade-analysis chart shows profit or loss per closed trade, cumulative
profit, profit by stock, and holding period. These charts help explain not
only whether the strategy made money, but also how consistently and with what
level of risk.

#### Portfolio, simulation, and fundamentals charts

Allocation charts show the weight of each stock and the sector allocation,
including cash. The red reference line makes a concentration problem visible.
The Monte Carlo fan chart shows a range of possible future portfolio paths and
the distribution of ending values. The random-portfolio frontier compares
annual return and volatility and highlights the best-Sharpe, lowest-risk, and
equal-weight portfolios.

The correlation heatmap shows how similarly stocks have moved. The normalised
price chart starts every stock at a value of 100 so that relative growth can be
compared fairly. Finally, the fundamentals scorecard displays which business
rules passed or failed, while the peer chart compares measures such as ROE,
operating margin, revenue growth, price-to-earnings, price-to-book, and
debt-to-equity.

### 5. Feedback received and changes implemented

The final version reflects feedback focused on making the project easier to
demonstrate, safer to use, and more clearly connected to the material learned
in class. The main changes are:

| Feedback or need | Change implemented |
|---|---|
| The project should still work when the market is closed or internet access is unavailable. | Added disk caching and an offline test/demo flow. Data can be prepared before class and reused from `data/cache/`. |
| Users need to see whether an order creates too much concentration. | Added the five-percent position cap, high-concentration warning, automatic cash reserve, and trimming of oversized winning positions. |
| The result should be understandable rather than only producing a final number. | Added descriptive statistics, risk-adjusted metrics, plain-English interpretation, CSV exports, and multiple charts. |
| The application should be accessible to both beginners and users who prefer a visual interface. | Kept the simple command-line menu and added a Streamlit dashboard with pages for the portfolio, stock analysis, backtest, statistics, and trade history. |
| The class should be able to see how Python libraries relate to basic Python code. | Added pandas, NumPy, and matplotlib reports and an explicit verification option comparing library results with hand-written calculations. |
| Backtesting must not accidentally use future prices. | Orders are queued after the close and filled at the next open; technical analysis only receives candles available up to the decision date. |
| The demonstration should be repeatable. | Added offline tests, fixed random seeds for Monte Carlo and random portfolios, and an updated step-by-step class demonstration in the README. |

These changes improved both the user experience and the educational value.
They also made potential weaknesses easier to identify instead of hiding them
behind an attractive chart or a single performance figure.

### 6. Testing, limitations, and conclusion

`test_offline.py` tests the application without internet access by replacing
the market-data functions with controlled fake data. It checks fundamentals,
technical indicators, strategy decisions, risk limits, trading hours, pending
orders, file saving, statistics, backtesting, chart generation, and agreement
between the hand-written and library calculations. This gives confidence that
the main educational workflows work consistently and do not depend on a live
market connection.

The results should still be interpreted carefully. Free APIs provide current
fundamentals, so applying today's fundamentals to historical prices introduces
look-ahead bias. The watchlist may also contain successful companies that
survived and performed well, creating survivorship bias. A two-year backtest is
only a small sample, and the simulator does not model every real-world effect,
including taxes, detailed slippage, liquidity constraints, and API failures.
The project is therefore best understood as a learning tool rather than proof
that the strategy will work in the future.

Overall, the project demonstrates a complete Python workflow: collecting and
caching data, transforming it into useful information, applying rules,
protecting a portfolio, simulating historical decisions, calculating
statistics, validating library results, and communicating findings through
charts and a dashboard. It connects classroom Python fundamentals with a
practical, modular application and provides a strong base for future work such
as improved historical fundamentals, more realistic transaction costs, and
additional strategy experiments.
