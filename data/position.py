# =====================
# Position model
# =====================
@dataclass
class Position:
    side: str              # "long" | "short"
    entry_price: float
    size: float
    leverage: float
    stop_pct: float
    opened_at: float
