"""Non-secret trading configuration.
Secrets belong in environment variables, not this file.
"""

# Exchange / runtime
EXCHANGE_ID = "binance"
EXECUTION_TIMEFRAME = "1m"
PAPER_TRADE = True
STARTING_CAPITAL = 1000.0
FETCH_TIMEOUT_MS = 20000
INTRA_CANDLE_SECONDS = 5

# Universe
QUOTE_CURRENCY = "USDT"
# The futures bot is currently being tested specifically on ETH/USDT. Pin the
# universe so scanner ranking cannot silently switch the paper test to ZEC or
# another higher-beta altcoin.
FAVOURITE_TOKENS = "ETH/USDT"
MIN_VOLUME_USDT = 10_000_000
TOP_CANDIDATE_COUNT = 10
SYMBOL_SCAN_INTERVAL_SECONDS = 60
# Keep ETH eligible; BTC remains excluded because this strategy is being
# evaluated on ETH rather than the deepest BTC market.
LARGE_CAP_BLACKLIST = {"BTC", "SOL", "XRP", "BNB"}

# Trading model: Donchian/Turtle-style breakout + trend filter + ATR risk management
# These periods are intentionally unchanged from the ZEC configuration: on a
# 1m execution strategy, 20/10 bars remain a sensible 20m breakout / 10m exit
# structure for ETH when higher-timeframe context controls direction.
WINDOW_SIZE = 250
DONCHIAN_ENTRY_PERIOD = 20
DONCHIAN_EXIT_PERIOD = 10
EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
ATR_PERIOD = 14
ADX_PERIOD = 14
MIN_ADX = 20.0
STRONG_ADX = 30.0
EXTREME_ADX = 40.0
# ETH is less jumpy than ZEC; require only a modest 50-minute directional move
# for the 1m regime, while the Donchian breakout remains the actual trigger.
MIN_TREND_PCT = 0.0015
MAX_ATR_PCT = 0.03
MIN_ATR_PCT = 0.0004
MIN_VOLUME_RATIO = 0.90
BREAKOUT_BUFFER_ATR = 0.08
MIN_TREND_AGE = 2

# Multi-timeframe regime confirmation: execution on 1m, context from closed 15m + 30m bars,
# with 60m used as the higher-timeframe directional safety layer.
MTF_ENABLED = True
MTF_TIMEFRAME_15M = "15m"
MTF_TIMEFRAME_30M = "30m"
MTF_TIMEFRAME_60M = "1h"
MTF_WINDOW_SIZE = 100
MTF_MIN_ADX = 18.0
# 0.2% over the 50-bar context is appropriate for a liquid major such as ETH;
# ADX + EMA alignment still prevents a flat market from being labelled trend.
MTF_MIN_TREND_PCT = 0.002
REQUIRE_MTF_ALIGNMENT = True
# 60m is deliberately a veto, not a fourth hard alignment requirement. A range/neutral
# hourly market must not suppress an otherwise valid 1m/15m/30m setup.
REQUIRE_60M_DIRECTIONAL_CONFIRMATION = False
VETO_60M_OPPOSITE_TREND = True

# Entry quality
REQUIRE_VOLUME_CONFIRMATION = True
REQUIRE_EMA_ALIGNMENT = True
REQUIRE_ADX_CONFIRMATION = True
ALLOW_LONG = True
ALLOW_SHORT = True
REQUIRE_DIRECTIONAL_CANDLE = True
MIN_DIRECTIONAL_CANDLE_BODY_PCT = 0.0004
MIN_ENTRY_CONFIDENCE = 0.45
SHORT_EXTRA_VOLUME_RATIO = 1.00
SHORT_EXTRA_ADX = 22.0
MIN_PRICE_TREND_PCT_FOR_ENTRY = 0.0015

# Risk / position sizing
RISK_PER_TRADE_PCT = 0.01
MAX_MARGIN_PCT = 0.30
# ETH's normal 1m ATR is generally tighter than ZEC's, so use a slightly tighter
# minimum and cap the initial stop before it becomes disproportionate to a major.
MIN_STOP_PCT = 0.0035
MAX_STOP_PCT = 0.018
STOP_ATR_MULTIPLIER = 1.50
STOP_SWING_LOOKBACK = 10
STOP_SWING_BUFFER_ATR = 0.15
REINVEST_PROFITS = True
TAKER_FEE_PCT = 0.001

# Leverage: deliberately low; only increase when the full MTF regime is objectively strong.
# ETH liquidity supports modest leverage, but 3x remains the absolute ceiling for paper testing.
BASE_LEVERAGE = 1.0
STRONG_TREND_LEVERAGE = 2.0
EXTREME_TREND_LEVERAGE = 3.0
MAX_LEVERAGE = 3.0

# Exit / trailing
TRAIL_ACTIVATION_R = 1.0
TRAIL_ATR_MULTIPLIER = 2.0
TRAIL_MIN_DISTANCE_PCT = 0.003
TRAIL_MAX_DISTANCE_PCT = 0.015
REVERSAL_CONFIRMATION_CANDLES = 2
EXIT_ON_OPPOSITE_BREAKOUT = True
EXIT_ON_EMA_REVERSAL = True
DONCHIAN_EXIT_MIN_R = 0.0

# Logging
LOG_DIRECTORY = "logs"
TRADE_LOG_FILENAME = "trades.csv"

# Email configuration is intentionally secret-free.
ENABLE_EMAIL = True
EMAIL_COOLDOWN_SECONDS = 3600
