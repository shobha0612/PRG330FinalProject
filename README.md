# Portfolio Management & Auto-Trading Simulator (Basic Python)

Educational project: virtual money only, free S&P 500 data via `yfinance`.

## Setup
```
pip install -r requirements.txt
python test_offline.py      # optional: proves everything works with fake data, no internet
python main.py
streamlit run app.py       # launch the browser dashboard
jupyter notebook main.ipynb # open the main program as a notebook
```

## Modules
| File | Job |
|---|---|
| config.py | all settings (5% cap, hours, files, thresholds) |
| data_fetcher.py | API calls + memory cache + disk cache for offline use |
| fundamentals.py | sector-specific business-quality rules |
| technicals.py | indicators, candle patterns, score |
| portfolio.py | holdings, allocation, JSON/CSV saving |
| risk_manager.py | 5% cap, High Concentration warning, trimming winners |
| order_engine.py | trading hours, orders, pending queue, trade log |
| strategy.py | fundamentals filter -> technicals -> decision |
| backtester.py | replays history day by day (works when the market is closed) |
| analytics.py | descriptive + quantitative statistics, report, CSV, charts |
| pandas_tools.py | pandas tables, indicators, screeners and CSV reports |
| numpy_stats.py | NumPy metrics, verification, Monte Carlo and random portfolios |
| charts.py | matplotlib dashboards, charts and HTML gallery |
| main.py | menu that connects everything |
| main.ipynb | notebook presentation of the main program |
| app.py | Streamlit dashboard for the portfolio, analysis, backtest, and statistics |

## Class demo script (market closed, works offline)
**Day before (with internet):** `python main.py` -> option **13** (saves data to `data/cache/`).

**In class:**
1. Option **10** - builds a starter portfolio at any time (weak companies skipped, each stock about 4%).
2. Option **1** - shows holdings and allocation %.
3. Option **3** with a very large quantity - shows the HIGH CONCENTRATION warning.
4. Option **2** (e.g. `AAPL`) - full fundamentals + technicals report.
5. Option **11** - backtest: report, `data/backtest_report.png`, `data/backtest_equity.csv`, `data/backtest_trades.csv`.
6. Option **12** (e.g. `NVDA`) - descriptive + quantitative statistics of one stock versus SPY.
7. Option **20** - draw a candlestick/indicator dashboard for one cached stock.
8. Option **21** - screen the watchlist, compare random portfolios and create a chart gallery.
9. Option **22** - view the current portfolio and its allocation charts.
10. Option **23** - create fundamentals scorecard and peer charts.
11. Option **24** - check the hand-written calculations against NumPy and pandas.

## Which library is used where

| Library | File | Purpose |
|---|---|---|
| pandas | `pandas_tools.py` | DataFrames, rolling indicators, monthly tables, correlations, screeners and CSV output |
| NumPy | `numpy_stats.py` | Vectorised metrics, verification, repeatable Monte Carlo paths and random portfolio weights |
| matplotlib | `charts.py` | Candlesticks, equity/risk charts, heatmaps, allocation charts and the chart gallery |

The hand-written versions in `analytics.py` and `technicals.py` are kept on purpose for learning.
They are not replaced: menu option **24** calculates the same values with NumPy/pandas and prints
the differences so students can see that the loops and library versions agree.

## Library chart list

The chart layer provides 13 separate charts: candlestick dashboard, equity dashboard, monthly
heatmap, return distribution, trade analysis, trade-plan outcomes, allocation charts, Monte Carlo
fan chart, random-portfolio frontier, correlation heatmap, normalised prices, fundamentals
scorecard, and fundamentals peer comparison. The generated PNG files are collected in an
`index.html` gallery.

## Updated class-demo script

**Day before (with internet):** run `python main.py` -> option **13** to save prices and
fundamentals in `data/cache/`.

**In class (offline):**
1. Option **10** builds a starter portfolio; weak companies are skipped.
2. Option **1** shows holdings and allocation.
3. Option **20** demonstrates the price, volume, RSI, MACD and trade-plan dashboard.
4. Option **21** demonstrates pandas screening, NumPy portfolio simulation and charts.
5. Option **22** charts the portfolio allocation (or explains when it is empty).
6. Option **23** shows a fundamentals scorecard and peer comparison.
7. Option **11** runs the original backtest report. Answer yes to the final library-analysis
   question for the pandas report, NumPy verification/Monte Carlo and chart gallery.
8. Option **24** explicitly demonstrates that the original loops and library calculations match.

## What the backtest report contains
* **Descriptive:** mean/median/std of daily returns, best/worst day and month, % up days, winning/losing streaks, skewness, kurtosis.
* **Quantitative:** total return, CAGR, volatility, Sharpe, Sortino, max drawdown, Calmar, VaR 95%, beta, alpha, correlation - strategy vs SPY buy-and-hold.
* **Trades:** win rate, profit factor, expectancy, average holding period, best/worst trade, profit by stock, fees paid.
* **Interpretation + limitations** written in plain English.

## Honest limitations
Free APIs only give today's fundamentals (look-ahead bias); the watchlist is made of today's winners
(survivorship bias); a 2-year test is a small sample; slippage and taxes are ignored.
