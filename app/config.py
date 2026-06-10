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


settings = Settings()
