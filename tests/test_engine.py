from __future__ import annotations

from pathlib import Path

from app import storage
from app.config import settings


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(settings, "db_path", str(tmp_path / "engine.sqlite3"))
    storage.init_db()


def test_buy_uses_ask_to_enter_and_bid_to_exit():
    pass  # Legacy test: PaperTradingEngine removed, logic now in multibot runtime
