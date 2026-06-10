from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "5050"))
    db_path: str = os.getenv("DB_PATH", "data/receiver.sqlite3")
    symbol: str = os.getenv("SYMBOL", "XAUUSD")
    initial_balance: float = float(os.getenv("INITIAL_BALANCE", "500.0"))
    max_spread: float = float(os.getenv("MAX_SPREAD", "1.5"))
    stale_tick_seconds: int = int(os.getenv("STALE_TICK_SECONDS", "10"))
    strategy_enabled: bool = _bool("STRATEGY_ENABLED", "false")
    swing_window: int = int(os.getenv("SWING_WINDOW", "3"))
    structure_scan_limit: int = int(os.getenv("STRUCTURE_SCAN_LIMIT", "1200"))
    ob_lookback: int = int(os.getenv("OB_LOOKBACK", "12"))
    impulse_body: float = float(os.getenv("IMPULSE_BODY", "1.5"))
    impulse_range: float = float(os.getenv("IMPULSE_RANGE", "1.5"))
    swing_tolerance: float = float(os.getenv("SWING_TOLERANCE", "0.3"))
    ob_strong_score: int = int(os.getenv("OB_STRONG_SCORE", "6"))
    # 0 keeps structural OB candidates until invalidated. Pending-order expiry
    # is added separately in v0.6 as an 8-candle execution rule.
    ob_max_age_candles: int = int(os.getenv("OB_MAX_AGE_CANDLES", "0"))


settings = Settings()
