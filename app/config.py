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
    swing_window: int = int(os.getenv("SWING_WINDOW", "3"))
    structure_scan_limit: int = int(os.getenv("STRUCTURE_SCAN_LIMIT", "1200"))
    ob_lookback: int = int(os.getenv("OB_LOOKBACK", "12"))
    impulse_body: float = float(os.getenv("IMPULSE_BODY", "1.5"))
    impulse_range: float = float(os.getenv("IMPULSE_RANGE", "1.5"))
    swing_tolerance: float = float(os.getenv("SWING_TOLERANCE", "0.3"))
    ob_strong_score: int = int(os.getenv("OB_STRONG_SCORE", "6"))
    ob_max_age_candles: int = int(os.getenv("OB_MAX_AGE_CANDLES", "0"))
    pending_timeframe: str = os.getenv("PENDING_TIMEFRAME", "M15")
    pending_expiry_candles: int = int(os.getenv("PENDING_EXPIRY_CANDLES", "8"))
    pending_min_rr: float = float(os.getenv("PENDING_MIN_RR", "1.5"))
    pending_tp_r_multiple: float = float(os.getenv("PENDING_TP_R_MULTIPLE", "2.0"))
    pending_sl_buffer_ratio: float = float(os.getenv("PENDING_SL_BUFFER_RATIO", "0.30"))
    pending_rejection_log_cooldown: int = int(os.getenv("PENDING_REJECTION_LOG_COOLDOWN", "60"))
    # Final-build paper execution. It is OFF by default for safety.
    auto_paper_enabled: bool = _bool("AUTO_PAPER_ENABLED", "false")
    trend_risk_percent: float = float(os.getenv("TREND_RISK_PERCENT", "0.01"))
    contract_size: float = float(os.getenv("CONTRACT_SIZE", "100.0"))
    lot_step: float = float(os.getenv("LOT_STEP", "0.01"))
    min_lot: float = float(os.getenv("MIN_LOT", "0.01"))
    max_lot: float = float(os.getenv("MAX_LOT", "10.0"))
    dashboard_username: str = os.getenv("DASHBOARD_USERNAME", "admin")
    dashboard_password: str = os.getenv("DASHBOARD_PASSWORD", "admin")


settings = Settings()
