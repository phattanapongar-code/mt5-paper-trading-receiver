from dataclasses import dataclass, field
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
    symbols: list[str] = field(default_factory=lambda: os.getenv("MT5_SYMBOLS", "XAUUSD").split(","))
    symbol: str = os.getenv("SYMBOL", "XAUUSD")
    initial_balance: float = float(os.getenv("INITIAL_BALANCE", "500.0"))
    max_spread: float = float(os.getenv("MAX_SPREAD", "1.5"))
    symbols_file_path: str = os.getenv("SYMBOLS_FILE_PATH", "symbols.json")
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

    # ── Execution Realism (Prop Firm Grade) ──
    commission_per_lot: float = float(os.getenv("COMMISSION_PER_LOT", "3.5"))
    commission_type: str = os.getenv("COMMISSION_TYPE", "fixed")
    commission_pct: float = float(os.getenv("COMMISSION_PCT", "0.0"))
    slippage_sigma: float = float(os.getenv("SLIPPAGE_SIGMA", "0.15"))
    slippage_max_pips: float = float(os.getenv("SLIPPAGE_MAX_PIPS", "0.5"))
    latency_ms_min: int = int(os.getenv("LATENCY_MS_MIN", "50"))
    latency_ms_max: int = int(os.getenv("LATENCY_MS_MAX", "200"))
    gap_check_enabled: bool = _bool("GAP_CHECK_ENABLED", "false")
    gap_max_percent: float = float(os.getenv("GAP_MAX_PERCENT", "0.5"))
    gap_threshold_seconds: int = int(os.getenv("GAP_THRESHOLD_SECONDS", "3600"))

    # ── Gap Auto-Fill (pull missing M1 candles from MT5 sender) ──
    sender_url: str = os.getenv("SENDER_URL", "")
    gap_auto_fill_enabled: bool = _bool("GAP_AUTO_FILL_ENABLED", "false")
    gap_fill_threshold_seconds: int = int(os.getenv("GAP_FILL_THRESHOLD_SECONDS", "300"))

    # ── Real Trading (trader.py) ──
    trade_host: str = os.getenv("TRADE_HOST", "0.0.0.0")
    trade_port: int = int(os.getenv("TRADE_PORT", "5051"))
    trade_api_key: str = os.getenv("TRADE_API_KEY", "")
    trade_magic: int = int(os.getenv("TRADE_MAGIC", "20240601"))
    trade_allowed_ips: list[str] = field(default_factory=lambda: os.getenv("TRADE_ALLOWED_IPS", "127.0.0.1").split(","))
    trade_webhook_url: str = os.getenv("TRADE_WEBHOOK_URL", "")
    trade_auto_retry_max: int = int(os.getenv("TRADE_AUTO_RETRY_MAX", "3"))


settings = Settings()
