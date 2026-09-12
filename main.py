import os
import time
import ccxt

from config.settings import *
from signals.signal_engine import SignalEngine
from strategy.strategy_manager import StrategyManager
from strategy.futures_trend_strategy import FuturesTrendStrategy
from trading.ccxtpapertradeexecutor import CCXTPaperTradeExecutor
from data_provider.ccxtdatafeed import CCXTDataFeed
from trading.tradingbot import TradingBot
from data.warmup import warmup_engine


def build_exchange():
    if EXCHANGE_ID != "binance":
        raise ValueError(f"Unsupported exchange: {EXCHANGE_ID}")
    params = {"enableRateLimit": True, "timeout": FETCH_TIMEOUT_MS}
    if not PAPER_TRADE:
        params["apiKey"] = os.getenv("BINANCE_API_KEY", "")
        params["secret"] = os.getenv("BINANCE_API_SECRET", "")
        if not params["apiKey"] or not params["secret"]:
            raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for live mode")
    return ccxt.binanceusdm(params)


def _to_candle(row):
    return {"timestamp": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]}


def _load_context(exchange, pair, timeframe, limit):
    rows = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit + 1)
    # Never use the currently forming higher-timeframe candle for a regime decision.
    return [_to_candle(row) for row in rows[:-1]]


def _apply_mtf(exchange, engine, symbol, pair):
    if not MTF_ENABLED:
        return
    candles_15m = _load_context(exchange, pair, MTF_TIMEFRAME_15M, MTF_WINDOW_SIZE)
    candles_30m = _load_context(exchange, pair, MTF_TIMEFRAME_30M, MTF_WINDOW_SIZE)
    candles_60m = _load_context(exchange, pair, MTF_TIMEFRAME_60M, MTF_WINDOW_SIZE)
    engine.update_mtf(symbol, candles_15m, candles_30m, candles_60m)


def _analyse_candidate(exchange, pair):
    symbol = pair.replace("/", "")
    rows = exchange.fetch_ohlcv(pair, timeframe=EXECUTION_TIMEFRAME, limit=WINDOW_SIZE + 1)
    engine = SignalEngine(WINDOW_SIZE)
    for row in rows[:-1]:
        engine.update(symbol, _to_candle(row))
    _apply_mtf(exchange, engine, symbol, pair)
    return engine.get_market_analysis(symbol)


def select_candidate(exchange):
    tickers = exchange.fetch_tickers()
    candidates = []
    for pair, ticker in tickers.items():
        if not pair.endswith(f"/{QUOTE_CURRENCY}"):
            continue
        base = pair.split("/")[0]
        if base in LARGE_CAP_BLACKLIST:
            continue
        volume = ticker.get("quoteVolume") or 0
        change = ticker.get("percentage")
        if change is None or volume < MIN_VOLUME_USDT:
            continue
        candidates.append((pair, float(change), float(volume)))

    candidates.sort(key=lambda item: abs(item[1]), reverse=True)
    ranked = []
    for pair, change, volume in candidates[:TOP_CANDIDATE_COUNT]:
        try:
            analysis = _analyse_candidate(exchange, pair)
            if analysis and analysis.should_trade:
                ranked.append((pair, change, volume, analysis))
        except Exception as exc:
            print(f"[SCAN] {pair}: {exc}")

    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[3].adx, abs(item[1])), reverse=True)
    selected = ranked[0]
    print(f"[SCAN] Selected {selected[0]} 24h={selected[1]:.2f}% regime={selected[3].gen_trend} "
          f"ADX={selected[3].adx:.1f} MTF15={selected[3].trend_15m} "
          f"MTF30={selected[3].trend_30m} MTF60={selected[3].trend_60m}")
    return selected[0]


def run_symbol(exchange, pair):
    stopped = {"value": False}

    def stop_flag():
        return stopped["value"]

    def on_trade_closed():
        stopped["value"] = True

    symbol = pair.replace("/", "")
    engine = SignalEngine(WINDOW_SIZE)
    manager = StrategyManager([FuturesTrendStrategy()])
    executor = CCXTPaperTradeExecutor()
    bot = TradingBot(engine, manager, executor, on_trade_closed=on_trade_closed)

    # Warm up 1m execution history and closed 15m/30m/60m context before allowing entries.
    _apply_mtf(exchange, engine, symbol, pair)
    warmup_engine(exchange, bot, symbol, pair)
    bot.set_ready()

    def on_candle(candle_symbol, candle):
        # Refresh all higher-timeframe context when a new 15m block starts. The
        # just-completed 15m, 30m and 60m candles are then available to the new 1m candle.
        if MTF_ENABLED and candle["timestamp"] % (15 * 60 * 1000) == 0:
            try:
                _apply_mtf(exchange, engine, symbol, pair)
            except Exception as exc:
                print(f"[MTF] {pair}: {exc}")
        bot.on_candle(candle_symbol, candle)

    feed = CCXTDataFeed(
        exchange,
        pair,
        EXECUTION_TIMEFRAME,
        on_candle,
        bot.on_price_tick,
        stop_flag=stop_flag,
    )
    print(f"[BOT] Binance USDT-M futures paper trading {pair} on {EXECUTION_TIMEFRAME}; MTF=15m+30m+60m")
    feed.start()


def main():
    print("[MAIN] Starting configurable futures trend-following bot (paper mode)")
    exchange = build_exchange()
    while True:
        try:
            pair = select_candidate(exchange)
            if not pair:
                print("[MAIN] No healthy MTF-aligned trend candidate; rescanning")
                time.sleep(SYMBOL_SCAN_INTERVAL_SECONDS)
                continue
            run_symbol(exchange, pair)
            time.sleep(2)
        except KeyboardInterrupt:
            print("[MAIN] Stopped by user")
            return
        except Exception as exc:
            print(f"[MAIN] {exc}")
            time.sleep(SYMBOL_SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
