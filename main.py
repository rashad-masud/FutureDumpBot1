import ccxt
import time
import sys
from config.settings import *
from signals.signal_engine import SignalEngine
from strategy.strategy_manager import StrategyManager
from strategy.dump_shorting_strategy import DumpShortingStrategy
from trading.ccxtpapertradeexecutor import CCXTPaperTradeExecutor
from data_provider.ccxtdatafeed import CCXTDataFeed
from trading.tradingbot import TradingBot
from data.warmup import warmup_engine
from utils.emailnotifier import send_email

def main():
    print("[MAIN] Starting Dump Trading Bot (Small Volatile Coins Only)")
    exchange = ccxt.binance({"enableRateLimit": True, "timeout": 20000})

    global stop_feed
    stop_feed = False

    def feed_stop_flag():
        return stop_feed

    def select_symbol():
        print("[SCAN] Fetching top gainers...")
        tickers = exchange.fetch_tickers()
        usdt_pairs = [s for s in tickers if s.endswith('/USDT')]

        candidates = []
        for pair in usdt_pairs:
            # Extract base currency (e.g., "BTC" from "BTC/USDT")
            base = pair.split('/')[0]
            # Skip blacklisted large caps
            if base in LARGE_CAP_BLACKLIST:
                continue

            t = tickers[pair]
            change = t.get('percentage')
            volume = t.get('quoteVolume', 0)
            if change is not None and volume >= MIN_VOLUME_USDT:
                candidates.append({
                    'symbol': pair.replace('/', ''),
                    'original_pair': pair,
                    'base': base,
                    'change_24h': change,
                    'volume': volume
                })

        if not candidates:
            print("[SCAN] No candidates found after filtering.")
            return None
        candidates.sort(key=lambda x: x['change_24h'], reverse=True)
        top_gainers = candidates[:TOP_GAINER_COUNT]

        dump_candidates = []
        for cand in top_gainers:
            sym = cand['symbol']
            orig_pair = cand['original_pair']
            try:
                ohlcv = exchange.fetch_ohlcv(orig_pair, timeframe='1h', limit=DUMP_LOOKBACK_CANDLES+5)
                if len(ohlcv) < DUMP_LOOKBACK_CANDLES:
                    continue
                candles = [{'timestamp': o[0], 'open': o[1], 'high': o[2], 'low': o[3], 'close': o[4], 'volume': o[5]} for o in ohlcv]
                temp_engine = SignalEngine(window_size=200)
                for c in candles:
                    temp_engine.update(sym, c)
                analysis = temp_engine.get_market_analysis(sym)
                if analysis and analysis.gen_trend == "dump":
                    strategy = DumpShortingStrategy()
                    if strategy.evaluate(candles, analysis):
                        dump_candidates.append(cand)
            except Exception as e:
                print(f"[SCAN] Error {sym}: {e}")

        if not dump_candidates:
            return None

        if len(dump_candidates) > 0:
            subject = "Multiple Dump Candidates"
            body = "Symbols in dump:\n" + "\n".join(f"- {c['symbol']}" for c in dump_candidates)
            send_email(subject, body)
            print("[SCAN] Multiple candidates, email sent.")

        best = max(dump_candidates, key=lambda x: x['change_24h'])
        print(f"[SCAN] Selected {best['symbol']} (base: {best['base']})")
        return best['symbol']

    def on_trade_closed():
        global stop_feed
        stop_feed = True
        print("[BOT] Trade closed, stopping feed.")

    def run_for_symbol(symbol):
        global stop_feed
        stop_feed = False

        if symbol.endswith('USDT'):
            symbol_with_slash = symbol[:-4] + '/' + symbol[-4:]
        else:
            symbol_with_slash = symbol

        engine = SignalEngine(window_size=200)
        manager = StrategyManager([DumpShortingStrategy()])
        executor = CCXTPaperTradeExecutor() if PAPER_TRADE else None  # Replace with live if needed
        bot = TradingBot(engine, manager, executor, on_trade_closed=on_trade_closed)

        warmup_engine(exchange, bot, symbol, symbol_with_slash)

        feed = CCXTDataFeed(
            exchange,
            symbol_with_slash,
            TIMEFRAME,
            bot.on_candle,
            bot.on_price_tick,
            stop_flag=feed_stop_flag
        )
        print(f"[LIVE] Trading {symbol}")
        feed.start()
        print(f"[LIVE] Stopped {symbol}")

    while True:
        try:
            sym = select_symbol()
            if not sym:
                print("[MAIN] No dump candidate. Wait 1 min.")
                time.sleep(60)
                continue
            run_for_symbol(sym)
            print("[MAIN] Trade finished. Rescanning...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("[MAIN] Stopped by user.")
            break
        except Exception as e:
            print(f"[MAIN] Unhandled error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    main()