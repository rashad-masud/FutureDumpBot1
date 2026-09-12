from types import SimpleNamespace

from trading.ccxttradeexecutorbase import CCXTTradeExecutorBase


class DummyExecutor(CCXTTradeExecutorBase):
    def _on_open(self, symbol, size, price, leverage, side):
        pass

    def _on_close(self, size, price, pnl, side):
        pass


def analysis(**overrides):
    values = dict(
        gen_trend="trend_down", should_trade=True, entry_breakout=True,
        mtf_aligned=True, adx=35.0, atr=1.0,
        exit_level_long=99.0, exit_level_short=101.0,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def candles():
    return [
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000.0}
    ] * 20


def test_leverage_requires_mtf_alignment():
    ex = DummyExecutor()
    assert ex._calculate_leverage(analysis(adx=45.0, mtf_aligned=False)) == 1.0
    assert ex._calculate_leverage(analysis(adx=45.0, mtf_aligned=True)) == 3.0


def test_stop_is_capped_by_risk_envelope():
    ex = DummyExecutor()
    result = ex._calculate_stop("short", 100.0, analysis(atr=1.0), candles())
    assert result is not None
    assert (result - 100.0) / 100.0 <= 0.025


def test_position_is_singleton():
    ex = DummyExecutor()
    ex.position = object()
    ex.execute("X/USDT", SimpleNamespace(signal_type=SimpleNamespace(value="short")), 100.0, analysis(), candles())
    assert ex.position is not None
