import csv
import os
import time
from config.settings import LOG_DIRECTORY, TRADE_LOG_FILENAME


class TradeJournal:
    def __init__(self):
        self.log_dir = LOG_DIRECTORY
        self.file_path = os.path.join(self.log_dir, TRADE_LOG_FILENAME)
        self._last_open = None          # stores the last opened trade data
        self._ensure_directory()
        self._ensure_file()

    def _ensure_directory(self):
        os.makedirs(self.log_dir, exist_ok=True)

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "trade_id",
                    "symbol",
                    "side",
                    "regime",
                    "entry_price",
                    "exit_price",
                    "size",
                    "leverage",
                    "stop_pct",
                    "pnl",
                    "balance_after",
                    "reason",
                    "open_candle_id",
                    "close_candle_id",
                    "open_tick_id",
                    "close_tick_id",
                ])

    # ---------- RECORD OPEN ----------
    def record_open(
        self,
        symbol,
        side,
        regime,
        entry_price,
        size,
        leverage,
        stop_pct,
        *,
        trade_id=None,
        open_candle_id=None,
        open_tick_id=None,
    ):
        """Store open trade details for later combination with close data."""
        self._last_open = {
            "timestamp": int(time.time()),
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "regime": regime,
            "entry_price": entry_price,
            "size": size,
            "leverage": leverage,
            "stop_pct": stop_pct,
            "open_candle_id": open_candle_id,
            "open_tick_id": open_tick_id,
        }
        print(f"[JOURNAL] Trade {trade_id} opened")

    # ---------- RECORD CLOSE ----------
    def record_close(
        self,
        *,
        trade_id=None,
        side=None,
        entry_price=None,
        exit_price=None,
        pnl=None,
        balance_after=None,
        reason=None,
        open_candle_id=None,
        close_candle_id=None,
        open_tick_id=None,
        close_tick_id=None,
    ):
        """Write the completed trade to the CSV file."""
        print(f"[JOURNAL] Trade {trade_id} closed, writing to log")

        # If we have stored open data for this trade, merge it
        open_data = self._last_open if self._last_open and self._last_open.get("trade_id") == trade_id else {}

        row = {
            "timestamp": int(time.time()),
            "trade_id": trade_id,
            "symbol": open_data.get("symbol", ""),
            "side": side or open_data.get("side", ""),
            "regime": open_data.get("regime", ""),
            "entry_price": entry_price or open_data.get("entry_price", ""),
            "exit_price": exit_price or "",
            "size": open_data.get("size", ""),
            "leverage": open_data.get("leverage", ""),
            "stop_pct": open_data.get("stop_pct", ""),
            "pnl": pnl or "",
            "balance_after": balance_after or "",
            "reason": reason or "",
            "open_candle_id": open_candle_id or open_data.get("open_candle_id", ""),
            "close_candle_id": close_candle_id or "",
            "open_tick_id": open_tick_id or open_data.get("open_tick_id", ""),
            "close_tick_id": close_tick_id or "",
        }

        # Append to the CSV file
        with open(self.file_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

        # Also keep in memory if needed
        self.trades.append(row)

        # Clear last_open to avoid accidental reuse
        self._last_open = None