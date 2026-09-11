import time
from config.settings import INTRA_CANDLE_SECONDS


class CCXTDataFeed:
    def __init__(self, exchange, symbol, timeframe, on_candle, on_price_tick, tick_interval=INTRA_CANDLE_SECONDS, stop_flag=None):
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.on_candle = on_candle
        self.on_price_tick = on_price_tick
        self.tick_interval = tick_interval
        self.stop_flag = stop_flag or (lambda: False)
        self.last_tick_time = 0
        self.last_candle_timestamp = None

    def start(self):
        while not self.stop_flag():
            now = time.time()
            if now - self.last_tick_time >= self.tick_interval:
                self.last_tick_time = now
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    if ticker.get("last") is not None:
                        self.on_price_tick(self.symbol.replace("/", ""), ticker["last"])
                except Exception as e:
                    print(f"[ERROR] Ticker: {e}")

            try:
                candles = self.exchange.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=2)
                if len(candles) < 2:
                    time.sleep(0.5)
                    continue
                ts, open_, high, low, close, volume = candles[-2]
                if self.last_candle_timestamp != ts:
                    self.last_candle_timestamp = ts
                    self.on_candle(
                        self.symbol.replace("/", ""),
                        {"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume},
                    )
            except Exception as e:
                print(f"[ERROR] OHLCV: {e}")
            time.sleep(0.5)
