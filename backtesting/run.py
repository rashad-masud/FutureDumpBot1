import logging

from backtesting.runner import BacktestRunner
from signals.signal_engine import SignalEngine
from trading.rmtradingbot import RMTradingBot
from config.settings import (
    TRADING_PAIRS,
    GEN_TREND_WINDOW_SIZE,
    GEN_TREND_THRESHOLD_PCT,
    STARTING_CAPITAL,
)

logger = logging.getLogger(__name__)


def run_backtest(historical_data: dict):
    """
    historical_data: dict[str, list]
    Example:
        {
            "ETH/USDT": [candle, candle, ...]
        }
    """

    for symbol in TRADING_PAIRS:
        candles = historical_data.get(symbol)

        if not candles:
            logger.warning("[BACKTEST] No data for %s, skipping", symbol)
            continue

        logger.info(
            "[BACKTEST] Running %s | candles=%d",
            symbol,
            len(candles),
        )

        signal_engine = SignalEngine(
            window_size=GEN_TREND_WINDOW_SIZE
        )

        bot = RMTradingBot(
            signal_engine=signal_engine,
            strategy_manager=strategy_manager,  # already constructed elsewhere
            capital=STARTING_CAPITAL,
            paper=True,
        )

        runner = BacktestRunner(
            symbol=symbol,
            candles=candles,
            signal_engine=signal_engine,
            bot=bot,
            gen_trend_window=GEN_TREND_WINDOW_SIZE,
            gen_trend_threshold=GEN_TREND_THRESHOLD_PCT,
        )

        runner.run()
