# -------------------- EXCHANGE --------------------
TIMEFRAME = "1m"                       # Candle timeframe
PAPER_TRADE = True                       # Paper trading for safety
STARTING_CAPITAL = 1000.0                 # Initial capital

# -------------------- FEES --------------------
TAKER_FEE_PCT = 0.001                    # 0.1% taker fee

# -------------------- RISK MANAGEMENT -------------
RISK_PER_TRADE_PCT = 0.02                # 2% of current balance risked per trade
MAX_TOTAL_EXPOSURE_PCT = 0.5              # Max 50% of balance in one position
MIN_STOP_PCT = 0.015                      # 1.5% minimum stop
MAX_STOP_PCT = 0.08                        # 8% maximum stop
VOL_STOP_MULTIPLIER = 2.5                  # Stop = volatility * multiplier
TRAIL_TRIGGER_PNL = 0.02                   # 2% profit to activate trailing
TRAIL_DISTANCE_PCT = 0.005                  # 0.5% trailing distance
REINVEST_PROFITS = True                     # Compound profits

# -------------------- REGIME DETECTION -----------
REGIME_LOOKBACK_CANDLES = 10
FAST_VOL_LOOKBACK = 3
MICRO_LOOKBACK = 5
MICRO_CONFIRMATION = 3
BREAKOUT_VOL_MULTIPLIER = 1.5
BREAKOUT_PRICE_CHANGE_PCT = 0.02
MIN_TREND_PCT = 0.04                         # 4% minimum trend
STRONG_TREND_THRESHOLD = 0.6                  # Require strong trend confirmation
EXTREME_VOLATILITY_THRESHOLD = 0.06
MAX_VOLATILITY_TO_AVOID = 0.10                 # Avoid extreme volatility above 10%
MAX_CONFIDENCE = 1.0
MIN_TREND_AGE_TO_TRADE = 2                     # Wait at least 2 candles in dump regime

# -------------------- DUMP DETECTION -------------
# More sensitive thresholds to catch deeper dumps after pumps
DUMP_LOOKBACK_CANDLES = 8                     # Look back 8 hours (was 5)
DUMP_CUMULATIVE_PCT = 0.05                    # 5% cumulative drop over 8 candles (was 8%)
DUMP_SINGLE_CANDLE_PCT = 0.04                  # 4% single candle drop (was 6%)
DUMP_RISK = True

# -------------------- TOP GAINER SCAN ------------
TOP_GAINER_LOOKBACK_HOURS = 12
TOP_GAINER_COUNT = 5
MIN_VOLUME_USDT = 1_000_000                    # Minimum 1M USDT volume (your requirement)

# Blacklist large-cap coins
LARGE_CAP_BLACKLIST = {"BTC", "ETH", "SOL", "XRP", "BNB"}

# -------------------- DUMP SHORTING STRATEGY -----
# No bounce requirement – enter immediately on dump confirmation
DUMP_CONFIRMATION_CANDLES = 2                  # Confirm over 2 candles
DUMP_MIN_DROP_PCT = 0.04                         # 4% drop over those 2 candles
DUMP_BOUNCE_REQUIRED = False                      # Disabled – enter immediately
DUMP_BOUNCE_THRESHOLD = 0.005                      # (unused)

# -------------------- LEVERAGE PROGRESSION ------
LEVERAGE_INITIAL = 3
LEVERAGE_STEP = 2
LEVERAGE_MAX = 7
LEVERAGE_RESET_ON_LOSS = True

# -------------------- PROFIT THRESHOLD ----------
MIN_PROFIT_PCT_TO_CONTINUE = 25.0                   # 25% minimum profit to keep leverage

# -------------------- REGIME SIZE MULTIPLIER -----
REGIME_SIZE_MULTIPLIER = {
    "dump": 1.2,
    "trend_down": 1.0,
    "range": 0.5,
    "volatile": 0.3,
    "breakout": 1.0,
}


# ==============================
# LOGGING & ALERTS
# ==============================
LOG_DIRECTORY = "logs"
TRADE_LOG_FILENAME = "trades.csv"

# -------------------- EMAIL ---------------------
ENABLE_EMAIL = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "rashad.masud@gmail.com"
SMTP_PASSWORD = "rzjb tawa uojx kfnq"
EMAIL_RECIPIENT = "rashad.masud@gmail.com"

# -------------------- TIMING --------------------
INTRA_CANDLE_SECONDS = 5