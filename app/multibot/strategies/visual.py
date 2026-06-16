from __future__ import annotations

import json
from typing import Any

from app import storage
from app.multibot.visual_engine import execute_graph


def decide(conn, bot: dict[str, Any], tick: dict[str, Any], params: dict[str, Any], now: int) -> dict[str, Any] | None:
    """Execute a visual (graph-based) strategy definition stored in bot parameters.

    The graph JSON is stored in bot['parameters_json']['graph'] as a serialised
    dict with keys ``nodes`` and ``edges``.
    """
    raw = bot.get("parameters_json")
    if not raw:
        return None
    try:
        p = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None

    graph = p.get("graph") if isinstance(p, dict) else None
    if not graph:
        return None

    bid = float(tick.get("bid", 0))
    ask = float(tick.get("ask", 0))
    if bid <= 0 or ask <= 0:
        return None

    return execute_graph(
        graph,
        bid=bid,
        ask=ask,
        symbol=str(bot.get("symbol", "XAUUSD")),
        timeframe=str(bot.get("timeframe", "M15")),
    )
