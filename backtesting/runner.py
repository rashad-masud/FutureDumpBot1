import logging
from core.enums import SignalType
from core.context import TradingContext

logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Controls the backtest loop.
    Owns GenTrend state.
    Uses the SAME bot + strategies as live mode.
    """

    def __init__(
        self,
        symbol: str,
        candles: list,
        signal_engine,
        bot,
        gen_trend_window: int,
        gen_trend_threshold: float,
    ):
        self.symbol = symbol
        self.candles = candles
        self.signal_engine = signal_engine
        self.bot = bot

        self.gen_trend_window = gen_trend_window
        self.gen_trend_threshold = gen_trend_threshold

        self.context = TradingContext()

    def run(self):
        logger.info(
            "[BACKTEST] Starting | candles=%d | GenTrendWindow=%d",
            len(self.candles),
            self.gen_trend_window,
        )

        for idx, candle in enumerate(self.candles):
            self.context.candle_index = idx

            # --- update rolling metrics ---
            self.signal_engine.update(self.symbol, candle)
            metrics = self.signal_engine.get_metrics(self.symbol)

            if metrics is None:
                logger.info("metrics is None")
                continue

            # --- update GenTrend every N candles ---
            if idx % self.gen_trend_window == 0:
                self.context.gen_trend = self._evaluate_gen_trend(metrics)
                logger.info(
                    "[GEN_TREND] candle=%d → %s (trend=%.2f%%)",
                    idx,
                    self.context.gen_trend.name,
                    metrics["trend_pct"] * 100,
                )

            # --- pass everything to bot ---
            self.bot.on_market_data(
                symbol=self.symbol,
                candle=candle,
                metrics=metrics,
                context=self.context,
            )

        logger.info("[BACKTEST] Finished")

    def _evaluate_gen_trend(self, metrics) -> SignalType:
        trend = metrics["trend_pct"]
        retVAL = SignalType.FLAT
        if trend > self.gen_trend_threshold:
            retVAL = SignalType.LONG
        elif trend < -self.gen_trend_threshold:
            retVAL = SignalType.SHORT
        else:
            retVAL = SignalType.FLAT


        logger.info("[BACKTEST] gen_trend:%d", retVAL)
        return retVAL;
