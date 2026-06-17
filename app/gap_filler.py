from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any

from app import storage
from app.candle_engine import CandleEngine
from app.config import settings

logger = logging.getLogger(__name__)

_TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}


def _fetch_history(symbol: str, from_ts: int, to_ts: int) -> list[dict[str, Any]]:
    url = f"{settings.sender_url}/api/history"
    params = f"?symbol={symbol}&from={from_ts}&to={to_ts}"
    try:
        resp = urllib.request.urlopen(url + params, timeout=10)
        data = json.loads(resp.read().decode())
        return data.get("candles") or []
    except Exception as exc:
        logger.warning("gap_filler: fetch failed for %s [%s-%s]: %s", symbol, from_ts, to_ts, exc)
        return []


def check_and_fill(candles_engine: CandleEngine, symbol: str, now: int) -> None:
    latest = storage.query_one(
        "SELECT open_time, close_time FROM candles WHERE symbol=? AND timeframe='M1' AND is_closed=1 ORDER BY open_time DESC LIMIT 1",
        (symbol,),
    )
    if not latest:
        return

    last_close = int(latest["close_time"])
    current_bucket = (now // 60) * 60

    if current_bucket - last_close <= settings.gap_fill_threshold_seconds:
        return

    from_ts = last_close
    to_ts = current_bucket
    rows = _fetch_history(symbol, from_ts, to_ts)
    if not rows:
        return

    result = candles_engine.import_m1_history(symbol, rows)
    logger.info(
        "gap_filler: filled %d M1 candles for %s [%s → %s], rebuilt=%s",
        len(rows), symbol, from_ts, to_ts, result,
    )

    from app.market_structure import structure
    from app.order_blocks import order_blocks

    structure.rebuild_all(symbol)
    order_blocks.rebuild_all(symbol)
