from config.settings import *
def warmup_engine(exchange, bot, internal_symbol, exchange_symbol):
    """
    internal_symbol: without slash (e.g., "BTCUSDT")
    exchange_symbol: with slash (e.g., "BTC/USDT")
    """
    ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=TIMEFRAME, limit=200)
    for candle in ohlcv:
        candle_dict = {
            'timestamp': candle[0],
            'open': candle[1],
            'high': candle[2],
            'low': candle[3],
            'close': candle[4],
            'volume': candle[5]
        }
        bot.on_candle(internal_symbol, candle_dict)   # bot expects symbol without slash