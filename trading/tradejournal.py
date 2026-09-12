import csv
import os
import time
from config.settings import LOG_DIRECTORY, TRADE_LOG_FILENAME


class TradeJournal:
    FIELDS = [
        "timestamp", "trade_id", "symbol", "side", "regime",
        "entry_price", "exit_price", "size", "leverage", "stop_pct",
        "pnl", "balance_after", "reason", "open_candle_id",
        "close_candle_id", "open_tick_id", "close_tick_id",
        "entry_fee", "exit_fee", "gross_pnl", "initial_stop",
        "best_price", "worst_price", "duration_seconds",
    ]

    def __init__(self):
        self.log_dir = LOG_DIRECTORY
        self.file_path = os.path.join(self.log_dir, TRADE_LOG_FILENAME)
        self._last_open = None
        self._closed_trade_ids = set()
        self._load_closed_trade_ids()
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(self.log_dir, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=self.FIELDS).writeheader()

    def _load_closed_trade_ids(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", newline="") as f:
                for row in csv.DictReader(f):
                    trade_id = row.get("trade_id")
                    if trade_id:
                        self._closed_trade_ids.add(str(trade_id))
        except (OSError, csv.Error):
            self._closed_trade_ids = set()

    def record_open(self, symbol, side, regime, entry_price, size, leverage, stop_pct, *, trade_id=None, open_candle_id=None, open_tick_id=None):
        self._last_open = {
            "trade_id": trade_id, "symbol": symbol, "side": side, "regime": regime,
            "entry_price": entry_price, "size": size, "leverage": leverage,
            "stop_pct": stop_pct, "open_candle_id": open_candle_id, "open_tick_id": open_tick_id,
        }

    def record_close(self, *, trade_id=None, side=None, entry_price=None, exit_price=None,
                     pnl=None, balance_after=None, reason=None, open_candle_id=None,
                     close_candle_id=None, open_tick_id=None, close_tick_id=None,
                     entry_fee=0.0, exit_fee=0.0, gross_pnl=0.0, initial_stop=None,
                     best_price=None, worst_price=None, leverage=None, duration_seconds=None):
        key = str(trade_id) if trade_id is not None else ""
        if key and key in self._closed_trade_ids:
            return False
        open_data = self._last_open or {}
        row = {
            "timestamp": int(time.time()), "trade_id": trade_id,
            "symbol": open_data.get("symbol", ""), "side": side or open_data.get("side", ""),
            "regime": open_data.get("regime", ""),
            "entry_price": entry_price if entry_price is not None else open_data.get("entry_price", ""),
            "exit_price": exit_price if exit_price is not None else "",
            "size": open_data.get("size", ""),
            "leverage": leverage if leverage is not None else open_data.get("leverage", ""),
            "stop_pct": open_data.get("stop_pct", ""),
            "pnl": pnl if pnl is not None else "", "balance_after": balance_after if balance_after is not None else "",
            "reason": reason or "",
            "open_candle_id": open_candle_id if open_candle_id is not None else open_data.get("open_candle_id", ""),
            "close_candle_id": close_candle_id or "",
            "open_tick_id": open_tick_id if open_tick_id is not None else open_data.get("open_tick_id", ""),
            "close_tick_id": close_tick_id or "",
            "entry_fee": entry_fee, "exit_fee": exit_fee, "gross_pnl": gross_pnl,
            "initial_stop": initial_stop if initial_stop is not None else "",
            "best_price": best_price if best_price is not None else "",
            "worst_price": worst_price if worst_price is not None else "",
            "duration_seconds": duration_seconds if duration_seconds is not None else "",
        }
        with open(self.file_path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=self.FIELDS).writerow(row)
        if key:
            self._closed_trade_ids.add(key)
        self._last_open = None
        return True
