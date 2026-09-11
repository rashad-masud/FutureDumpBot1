from core.enums import SignalType
from config.settings import (
    DUMP_CONFIRMATION_CANDLES,
    DUMP_MIN_DROP_PCT,
    DUMP_BOUNCE_REQUIRED,
    DUMP_BOUNCE_THRESHOLD,
    DUMP_RISK,
)

class DumpShortingStrategy:
    """
    Shorts only during a confirmed dump/free fall.
    """
    supported_regimes = {"dump"}   # only act when signal engine says "dump"

    def evaluate(self, candles, analysis):
        if not DUMP_RISK:
            return None

        # 1️⃣ Confirm dump with price action
        if not self._is_dump_confirmed(candles, analysis):
            return None

        # 2️⃣ Wait for a small bounce to avoid shorting the very bottom
        if DUMP_BOUNCE_REQUIRED and not self._has_bounced(candles):
            return None

        return SignalType.SHORT

    def _is_dump_confirmed(self, candles, analysis):
        if len(candles) < DUMP_CONFIRMATION_CANDLES:
            return False
        recent = candles[-DUMP_CONFIRMATION_CANDLES:]
        start_close = recent[0]["close"]
        end_close = recent[-1]["close"]
        drop = (start_close - end_close) / start_close
        return drop >= DUMP_MIN_DROP_PCT

    def _has_bounced(self, candles):
        last = candles[-1]
        bounce = (last["close"] - last["open"]) / last["open"]
        return bounce >= DUMP_BOUNCE_THRESHOLD