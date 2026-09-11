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


def symbol_with_quote(symbol):
    return symbol if "/" in symbol else f"{symbol}/{QUOTE_CURRENCY}"


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

    candidates.sort(key=lambda x: abs(x[1]), reverse=True)
    strategy = FuturesTrendStrategy()
    ranked = []
    for pair, change, volume in candidates[:TOP_CANDIDATE_COUNT]:
        try:
            symbol = pair.replace("/", "")
            ohlcv = exchange.fetch_ohlcv(pair, timeframe=EXECUTION_TIMEFRAME, limit=WINDOW_SIZE + 1)
            engine = SignalEngine(WINDOW_SIZE)
            for row in ohlcv[:-1]:
                engine.update(symbol, {"timestamp": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]})
            analysis = engine.get_market_analysis(symbol)
            if analysis and analysis.should_trade:
                signal = strategy.evaluate(list(engine.candles[symbol]), analysis)
                if signal:
                    ranked.append((pair, change, volume, analysis))
        except Exception as exc:
            print(f"[SCAN] {pair}: {exc}")

    if not ranked:
        return None
    ranked.sort(key=lambda item: abs(item[1]), reverse=True)
    selected = ranked[0]
    print(
        f"[SCAN] Selected {selected[0]} 24h={selected[1]:.2f}% "
        f"regime={selected[3].gen_trend} ADX={selected[3].adx:.1f}"
    )
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

    warmup_engine(exchange, bot, symbol, pair)
    feed = CCXTDataFeed(
        exchange,
        pair,
        EXECUTION_TIMEFRAME,
        bot.on_candle,
        bot.on_price_tick,
        stop_flag=stop_flag,
    )
    print(f"[BOT] Futures paper trading {pair} on {EXECUTION_TIMEFRAME}")
    feed.start()


def main():
    print("[MAIN] Starting configurable futures trend-following bot (paper mode)")
    exchange = build_exchange()
    while True:
        try:
            pair = select_candidate(exchange)
            if not pair:
                print("[MAIN] No healthy breakout candidate; rescanning")
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
