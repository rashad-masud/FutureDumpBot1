import csv
import os
import time
from config.settings import LOG_DIRECTORY, TRADE_LOG_FILENAME


class TradeJournal:
    """Durable, idempotent journal containing actual trade lifecycle events."""

    FIELDS = [
        "timestamp", "event", "trade_id", "symbol", "side", "regime",
        "entry_price", "exit_price", "size", "leverage", "stop_pct",
        "pnl", "balance_after", "reason", "open_candle_id",
        "close_candle_id", "open_tick_id", "close_tick_id",
    ]

    def __init__(self):
        self.log_dir = LOG_DIRECTORY
        self.file_path = os.path.join(self.log_dir, TRADE_LOG_FILENAME)
        self._open_trades = {}
        self._closed_trade_ids = set()
        self._load_state()
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(self.log_dir, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self.FIELDS).writeheader()

    def _load_state(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    trade_id = str(row.get("trade_id") or "").strip()
                    if not trade_id:
                        continue
                    event = str(row.get("event") or "EXIT").upper()
                    if event == "ENTRY":
                        self._open_trades[trade_id] = row
                    elif event == "EXIT":
                        self._closed_trade_ids.add(trade_id)
                        self._open_trades.pop(trade_id, None)
        except (OSError, csv.Error):
            self._open_trades.clear()
            self._closed_trade_ids.clear()

    def _append(self, row):
        with open(self.file_path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.FIELDS).writerow(row)

    def record_open(self, symbol, side, regime, entry_price, size, leverage, stop_pct, *, trade_id=None, open_candle_id=None, open_tick_id=None):
        """Write exactly one ENTRY event for a new trade."""
        key = str(trade_id) if trade_id is not None else ""
        if not key or key in self._open_trades or key in self._closed_trade_ids:
            return False

        row = {
            "timestamp": int(time.time()), "event": "ENTRY", "trade_id": key,
            "symbol": symbol, "side": side, "regime": regime or "",
            "entry_price": entry_price, "exit_price": "", "size": size,
            "leverage": leverage, "stop_pct": stop_pct, "pnl": "",
            "balance_after": "", "reason": "",
            "open_candle_id": open_candle_id if open_candle_id is not None else "",
            "close_candle_id": "",
            "open_tick_id": open_tick_id if open_tick_id is not None else "",
            "close_tick_id": "",
        }
        self._append(row)
        self._open_trades[key] = row
        return True

    def record_close(self, *, trade_id=None, side=None, entry_price=None, exit_price=None, pnl=None, balance_after=None, reason=None, open_candle_id=None, close_candle_id=None, open_tick_id=None, close_tick_id=None):
        """Write exactly one EXIT event for an open trade."""
        key = str(trade_id) if trade_id is not None else ""
        if not key or key in self._closed_trade_ids:
            return False

        open_data = self._open_trades.get(key, {})
        row = {
            "timestamp": int(time.time()), "event": "EXIT", "trade_id": key,
            "symbol": open_data.get("symbol", ""),
            "side": side or open_data.get("side", ""),
            "regime": open_data.get("regime", ""),
            "entry_price": entry_price if entry_price is not None else open_data.get("entry_price", ""),
            "exit_price": exit_price if exit_price is not None else "",
            "size": open_data.get("size", ""),
            "leverage": open_data.get("leverage", ""),
            "stop_pct": open_data.get("stop_pct", ""),
            "pnl": pnl if pnl is not None else "",
            "balance_after": balance_after if balance_after is not None else "",
            "reason": reason or "",
            "open_candle_id": open_candle_id if open_candle_id is not None else open_data.get("open_candle_id", ""),
            "close_candle_id": close_candle_id if close_candle_id is not None else "",
            "open_tick_id": open_tick_id if open_tick_id is not None else open_data.get("open_tick_id", ""),
            "close_tick_id": close_tick_id if close_tick_id is not None else "",
        }
        self._append(row)
        self._closed_trade_ids.add(key)
        self._open_trades.pop(key, None)
        return True
