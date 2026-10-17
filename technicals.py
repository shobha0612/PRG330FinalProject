# technicals.py
# MODULE 4 - Judges the PRICE CHART: trend, momentum, volume and candle patterns.
# Concepts used: lists, for loops, slicing, if/elif/else, math, functions
#
# Every indicator is written by hand with simple loops (no pandas needed),
# so you can see exactly how each one is calculated.

import config


# ===========================================================================
# PART 1 - INDICATORS
# ===========================================================================
def sma(values, period):
    """Simple Moving Average = average of the last `period` values."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values, period):
    """Exponential Moving Average for every point (recent prices weigh more)."""
    multiplier = 2 / (period + 1)
    result = []
    for i in range(len(values)):
        if i == 0:
            result.append(values[0])
        else:
            result.append(values[i] * multiplier + result[-1] * (1 - multiplier))
    return result


def rsi(closes, period=14):
    """Relative Strength Index (0-100). >70 overbought, <30 oversold."""
    if len(closes) < period + 1:
        return None
    gains = 0
    losses = 0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains = gains + change
        else:
            losses = losses - change
    avg_gain = gains / period
    avg_loss = losses / period

    # Wilder's smoothing for the rest of the data
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = change if change > 0 else 0
        loss = -change if change < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(closes):
    """MACD = EMA12 - EMA26, signal line = EMA9 of MACD. Returns today and yesterday."""
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    macd_line = []
    for i in range(len(closes)):
        macd_line.append(ema12[i] - ema26[i])
    signal_line = ema_series(macd_line, 9)
    return {
        "macd": macd_line[-1], "signal": signal_line[-1],
        "prev_macd": macd_line[-2], "prev_signal": signal_line[-2],
    }


def bollinger(values, period=20, num_std=2):
    """Bollinger Bands = SMA20 +/- 2 standard deviations. Returns upper, middle, lower, width."""
    window = values[-period:]
    middle = sum(window) / period
    total = 0
    for price in window:
        total = total + (price - middle) ** 2
    std = (total / period) ** 0.5
    upper = middle + num_std * std
    lower = middle - num_std * std
    width = (upper - lower) / middle
    return upper, middle, lower, width


def stochastic(highs, lows, closes, period=14):
    """Stochastic %K (0-100). <20 oversold, >80 overbought."""
    highest = max(highs[-period:])
    lowest = min(lows[-period:])
    if highest == lowest:
        return 50.0
    return (closes[-1] - lowest) / (highest - lowest) * 100


def obv_series(closes, volumes):
    """On-Balance Volume: add volume on up days, subtract it on down days."""
    obv = [0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return obv


def percent_change(values, days):
    """Percent change over the last `days` candles."""
    if len(values) <= days:
        return 0.0
    return (values[-1] / values[-1 - days] - 1) * 100


# ===========================================================================
# PART 2 - CANDLESTICK PATTERNS
# ===========================================================================
def detect_candle_patterns(o, h, l, c):
    """
    Looks at the last 1-3 candles. Returns a list of (pattern name, points).
    Positive points = bullish, negative = bearish.
    """
    patterns = []
    if len(c) < 7:
        return patterns

    # --- measurements of the latest candle ---
    body = abs(c[-1] - o[-1])
    full_range = h[-1] - l[-1]
    if full_range == 0:
        return patterns
    upper_shadow = h[-1] - max(o[-1], c[-1])
    lower_shadow = min(o[-1], c[-1]) - l[-1]

    prior_down = c[-2] < c[-6]        # were prices falling before this candle?
    prior_up = c[-2] > c[-6]          # were prices rising before this candle?

    # 1. Doji: open and close almost equal -> indecision
    if body <= 0.1 * full_range:
        patterns.append(("Doji (indecision)", 0))

    # 2. Hammer: long lower shadow after a fall -> buyers stepping in
    if body > 0 and lower_shadow >= 2 * body and upper_shadow <= 0.5 * body and prior_down:
        patterns.append(("Hammer (bullish reversal)", 1))

    # 3. Shooting star: long upper shadow after a rise -> sellers stepping in
    if body > 0 and upper_shadow >= 2 * body and lower_shadow <= 0.5 * body and prior_up:
        patterns.append(("Shooting Star (bearish reversal)", -1))

    # 4. Engulfing: today's body swallows yesterday's body
    prev_red = c[-2] < o[-2]
    prev_green = c[-2] > o[-2]
    today_green = c[-1] > o[-1]
    today_red = c[-1] < o[-1]
    if prev_red and today_green and o[-1] <= c[-2] and c[-1] >= o[-2] and prior_down:
        patterns.append(("Bullish Engulfing", 2))
    if prev_green and today_red and o[-1] >= c[-2] and c[-1] <= o[-2] and prior_up:
        patterns.append(("Bearish Engulfing", -2))

    # 5. Morning / Evening star (3 candles)
    first_body = abs(c[-3] - o[-3])
    second_body = abs(c[-2] - o[-2])
    first_mid = (o[-3] + c[-3]) / 2
    if c[-3] < o[-3] and second_body < 0.3 * first_body and today_green and c[-1] > first_mid:
        patterns.append(("Morning Star (bullish reversal)", 2))
    if c[-3] > o[-3] and second_body < 0.3 * first_body and today_red and c[-1] < first_mid:
        patterns.append(("Evening Star (bearish reversal)", -2))

    # 6. Three white soldiers / three black crows (strong trends)
    if (c[-1] > o[-1] and c[-2] > o[-2] and c[-3] > o[-3]
            and c[-1] > c[-2] > c[-3] and o[-1] > o[-2] > o[-3]):
        patterns.append(("Three White Soldiers (strong up-move)", 2))
    if (c[-1] < o[-1] and c[-2] < o[-2] and c[-3] < o[-3]
            and c[-1] < c[-2] < c[-3] and o[-1] < o[-2] < o[-3]):
        patterns.append(("Three Black Crows (strong down-move)", -2))

    return patterns


# ===========================================================================
# PART 3 - SCORING
# ===========================================================================
def add_score(result, points, text):
    """Adds points to the score and remembers WHY (so the user can read the reasons)."""
    result["score"] = result["score"] + points
    if points > 0:
        result["reasons"].append("+" + str(points) + "  " + text)
    elif points < 0:
        result["reasons"].append(str(points) + "  " + text)
    else:
        result["reasons"].append(" 0  " + text)


def analyze_technicals(data):
    """
    Takes the price-history dictionary from data_fetcher and returns:
        score, signal (BUY/SELL/HOLD), reasons, states, indicators, patterns
    """
    # Indicators only need recent data; the all-time high needs ALL data
    all_closes = data["close"]
    o = data["open"][-400:]
    h = data["high"][-400:]
    l = data["low"][-400:]
    c = data["close"][-400:]
    v = data["volume"][-400:]
    price = c[-1]

    result = {"price": price, "score": 0, "reasons": [], "states": [],
              "patterns": [], "indicators": {}, "signal": "HOLD"}
    ind = result["indicators"]
    falling_knife = False

    # ---------- 1. Trend: moving averages ----------
    ind["sma20"] = sma(c, 20)
    ind["sma50"] = sma(c, 50)
    ind["sma200"] = sma(c, 200)
    if ind["sma50"] and ind["sma200"]:
        if price > ind["sma50"] > ind["sma200"]:
            add_score(result, 2, "Uptrend: price above SMA50 above SMA200")
        elif price < ind["sma50"] < ind["sma200"]:
            add_score(result, -2, "Downtrend: price below SMA50 below SMA200")
        # Golden cross / death cross in the last 5 days
        old50 = sma(c[:-5], 50)
        old200 = sma(c[:-5], 200)
        if old50 and old200:
            if old50 <= old200 and ind["sma50"] > ind["sma200"]:
                add_score(result, 2, "GOLDEN CROSS: SMA50 just crossed above SMA200")
            if old50 >= old200 and ind["sma50"] < ind["sma200"]:
                add_score(result, -2, "DEATH CROSS: SMA50 just crossed below SMA200")

    # ---------- 2. Momentum: RSI ----------
    ind["rsi"] = rsi(c)
    if ind["rsi"] is not None:
        if ind["rsi"] < 30:
            add_score(result, 1, "RSI " + str(round(ind["rsi"])) + ": oversold, bounce possible")
        elif ind["rsi"] > 70:
            add_score(result, -1, "RSI " + str(round(ind["rsi"])) + ": overbought")

    # ---------- 3. MACD ----------
    m = macd(c)
    ind["macd"] = m["macd"]
    ind["macd_signal"] = m["signal"]
    if m["macd"] > m["signal"]:
        add_score(result, 1, "MACD above signal line (bullish momentum)")
        if m["prev_macd"] <= m["prev_signal"]:
            add_score(result, 1, "MACD just crossed UP")
    else:
        add_score(result, -1, "MACD below signal line (bearish momentum)")
        if m["prev_macd"] >= m["prev_signal"]:
            add_score(result, -1, "MACD just crossed DOWN")

    # ---------- 4. Bollinger Bands ----------
    upper, middle, lower, width = bollinger(c)
    ind["bb_upper"] = upper
    ind["bb_lower"] = lower
    if price < lower:
        add_score(result, 1, "Price below lower Bollinger Band (stretched down)")
    elif price > upper:
        add_score(result, -1, "Price above upper Bollinger Band (stretched up)")

    # Squeeze: bands much narrower than usual -> a big move is coming (direction unknown)
    widths = []
    for k in range(100):
        end = len(c) - k
        widths.append(bollinger(c[:end])[3])
    average_width = sum(widths) / len(widths)
    if width < 0.8 * average_width:
        result["states"].append("BOLLINGER SQUEEZE (breakout building)")

    # ---------- 5. Stochastic ----------
    ind["stoch"] = stochastic(h, l, c)
    if ind["stoch"] < 20:
        add_score(result, 1, "Stochastic " + str(round(ind["stoch"])) + ": oversold")
    elif ind["stoch"] > 80:
        add_score(result, -1, "Stochastic " + str(round(ind["stoch"])) + ": overbought")

    # ---------- 6. Volume ----------
    average_volume = sum(v[-21:-1]) / 20
    ind["volume_ratio"] = 1.0
    if average_volume > 0:
        ind["volume_ratio"] = v[-1] / average_volume
    if ind["volume_ratio"] > 1.5:
        if c[-1] > o[-1]:
            add_score(result, 1, "High volume on a green candle (strong buying)")
        else:
            add_score(result, -1, "High volume on a red candle (strong selling)")

    # ---------- 7. Accumulation / Distribution (On-Balance Volume) ----------
    obv = obv_series(c, v)
    change_20d = percent_change(c, 20)
    obv_rising = obv[-1] > obv[-21]
    if obv_rising and -3 <= change_20d <= 5:
        result["states"].append("ACCUMULATION (volume flowing in, price still flat)")
        add_score(result, 2, "Accumulation: OBV rising while price is flat")
    elif (not obv_rising) and change_20d >= 0:
        result["states"].append("DISTRIBUTION (price up but volume flowing out)")
        add_score(result, -2, "Distribution: OBV falling while price is rising")

    # ---------- 8. Highs and lows ----------
    all_time_high = max(all_closes)
    last_year = c[-252:]
    year_high = max(last_year)
    year_low = min(last_year)
    ind["all_time_high"] = all_time_high
    ind["year_high"] = year_high
    ind["year_low"] = year_low

    if price >= 0.995 * all_time_high:
        result["states"].append("AT ALL-TIME HIGH")
        if ind["rsi"] is not None and ind["rsi"] > 70:
            add_score(result, -1, "At all-time high but overbought: wait for a pullback")
        else:
            add_score(result, 1, "Breakout at all-time high with room to run")
    elif price >= 0.95 * all_time_high:
        result["states"].append("NEAR ALL-TIME HIGH")
    if price <= 1.05 * year_low:
        result["states"].append("NEAR 52-WEEK LOW")

    # ---------- 9. Aggressive fall detector ----------
    change_1d = percent_change(c, 1)
    change_5d = percent_change(c, 5)
    ind["change_1d"] = change_1d
    ind["change_5d"] = change_5d
    if change_1d <= -5 or change_5d <= -10:
        falling_knife = True
        result["states"].append("AGGRESSIVE FALL (falling knife)")
        add_score(result, -3, "Falling fast: " + str(round(change_1d, 1)) + "% today, "
                  + str(round(change_5d, 1)) + "% in 5 days")

    # ---------- 10. Candlestick patterns ----------
    found = detect_candle_patterns(o, h, l, c)
    for name, points in found:
        result["patterns"].append(name)
        add_score(result, points, "Candle pattern: " + name)

    # ---------- Final signal ----------
    if result["score"] >= config.BUY_SCORE and not falling_knife:
        result["signal"] = "BUY"
    elif result["score"] <= config.SELL_SCORE:
        result["signal"] = "SELL"
    else:
        result["signal"] = "HOLD"
    return result


def print_technical_report(symbol, result):
    ind = result["indicators"]
    print("\n--- TECHNICALS: " + symbol + " ---")
    print("Price:", round(result["price"], 2))
    print("SMA20:", rnd(ind["sma20"]), "| SMA50:", rnd(ind["sma50"]), "| SMA200:", rnd(ind["sma200"]))
    print("RSI:", rnd(ind["rsi"]), "| Stochastic:", rnd(ind["stoch"]),
          "| Volume vs 20-day avg:", rnd(ind["volume_ratio"]) + "x")
    print("Bollinger lower/upper:", rnd(ind["bb_lower"]), "/", rnd(ind["bb_upper"]))
    print("All-time high:", rnd(ind["all_time_high"]), "| 52w range:",
          rnd(ind["year_low"]), "-", rnd(ind["year_high"]))
    if len(result["states"]) > 0:
        print("States:", " | ".join(result["states"]))
    print("Score breakdown:")
    for line in result["reasons"]:
        print("   ", line)
    print("TECHNICAL SCORE:", result["score"], "->", result["signal"])


def rnd(value):
    if value is None:
        return "n/a"
    return str(round(value, 2))
