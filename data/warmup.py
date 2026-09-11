from config.settings import EXECUTION_TIMEFRAME, WINDOW_SIZE


def warmup_engine(exchange, bot, internal_symbol, exchange_symbol):
    ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=EXECUTION_TIMEFRAME, limit=WINDOW_SIZE + 1)
    for candle in ohlcv[:-1]:
        bot.on_candle(
            internal_symbol,
            {
                "timestamp": candle[0],
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5],
            },
        )
