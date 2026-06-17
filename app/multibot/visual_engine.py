from __future__ import annotations

import math
from collections import deque
from typing import Any, Callable

from app import storage
from app.indicators import sma, rsi, atr, ema, compute_indicators, bollinger_bands, macd as macd_func, trend_from_ma


# ── Node handler registry ──

NodeHandler = Callable[[dict[str, Any], list[Any], dict[str, Any]], Any]
_registry: dict[str, NodeHandler] = {}

# Persistent cross-detection state across ticks (keyed by node_id:symbol:timeframe)
_cross_state: dict[str, Any] = {}


def register_node(node_type: str) -> Callable:
    def wrapper(fn: NodeHandler) -> NodeHandler:
        _registry[node_type] = fn
        return fn
    return wrapper


def get_node_types() -> dict[str, str]:
    return {
        "data_source": "Market data source (latest candle OHLC)",
        "sma": "Simple Moving Average",
        "rsi": "Relative Strength Index",
        "atr": "Average True Range",
        "ema": "Exponential Moving Average",
        "compare": "Compare two values (>, <, >=, <=, ==, cross_above, cross_below, cross_above_threshold, cross_below_threshold)",
        "and": "Logical AND of multiple boolean inputs",
        "or": "Logical OR of multiple boolean inputs",
        "not": "Logical NOT of a boolean input",
        "order": "Generate buy/sell decision (supports OB entry via 2nd input)",
        "trend": "Trend direction from MA60/MA80/MA300 (BULLISH/BEARISH/NEUTRAL/WARMING_UP)",
        "ob_query": "Query latest active strong order block from DB",
        "bollinger": "Bollinger Bands (upper/middle/lower)",
        "macd": "MACD line, signal line, histogram",
        "value": "Constant value from params (for thresholds, trend strings, etc.)",
        "field": "Extract a named field from a dict input",
        "price": "Current tick price (mid/bid/ask via param value)",
        "ob_in_range": "Check if price is within OB zone (ob_low <= price <= ob_high)",
        "ob_not_stale": "Check if OB is not older than max_age_candles param",
    }


# ── Helpers ──

def _closes(symbol: str, timeframe: str, limit: int = 320) -> list[float]:
    rows = storage.query_all(
        "SELECT close FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT ?",
        (symbol, timeframe, limit),
    )
    return [r["close"] for r in reversed(rows)]


def _candles(symbol: str, timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = storage.query_all(
        "SELECT open, high, low, close FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT ?",
        (symbol, timeframe, limit),
    )
    return list(reversed(rows))


def _ohlc_candles(symbol: str, timeframe: str, limit: int = 320) -> list[dict[str, Any]]:
    rows = storage.query_all(
        "SELECT open, high, low, close, is_closed FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT ?",
        (symbol, timeframe, limit),
    )
    return list(reversed(rows))


def _latest_candle(symbol: str, timeframe: str) -> dict[str, Any] | None:
    return storage.query_one(
        "SELECT open, high, low, close, volume FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT 1",
        (symbol, timeframe),
    )


def _atr_value(symbol: str, timeframe: str, period: int = 14) -> float | None:
    cs = _candles(symbol, timeframe, period + 5)
    if len(cs) < period + 1:
        return None
    return atr(cs, period)


def _pip_value(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s or "XAG" in s:
        return 0.1
    return 0.0001


def _get_ob_input(inputs: list[Any]) -> dict[str, Any] | None:
    for v in inputs[1:]:
        if isinstance(v, dict) and "ob_low" in v and "ob_high" in v:
            return v
    return None


# ── Node handlers ──


def _params(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("params") or node.get("data", {}).get("params") or {}


@register_node("data_source")
def _handle_data_source(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Provide latest candle data. Stores symbol/timeframe in context for downstream."""
    p = _params(node)
    symbol = str(p.get("symbol", ctx.get("_symbol", "XAUUSD")))
    timeframe = str(p.get("timeframe", ctx.get("_timeframe", "M15")))
    candle = _latest_candle(symbol, timeframe)
    if not candle:
        return None
    return {
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "volume": candle.get("volume", 0),
        "timestamp": candle.get("open_time", 0),
        "_symbol": symbol,
        "_timeframe": timeframe,
    }


@register_node("sma")
def _handle_sma(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> float | None:
    p = _params(node)
    period = int(p.get("period", 14))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    cs = _closes(symbol, timeframe, period + 5)
    return sma(cs, period)


@register_node("rsi")
def _handle_rsi(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> float | None:
    p = _params(node)
    period = int(p.get("period", 14))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    cs = _closes(symbol, timeframe, period + 5)
    return rsi(cs, period)


@register_node("atr")
def _handle_atr(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> float | None:
    p = _params(node)
    period = int(p.get("period", 14))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    return _atr_value(symbol, timeframe, period)


@register_node("ema")
def _handle_ema(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> float | None:
    p = _params(node)
    period = int(p.get("period", 14))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    cs = _closes(symbol, timeframe, period + 5)
    result = ema(cs, period)
    return result[-1] if result else None


# ── New indicator nodes ──


@register_node("trend")
def _handle_trend(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> str:
    """Trend direction from MA60/MA80/MA300."""
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    candles = _ohlc_candles(symbol, timeframe, 300)
    if len(candles) < 60:
        return "WARMING_UP"
    result = compute_indicators(candles)
    return str(result.get("trend", "NEUTRAL"))


@register_node("ob_query")
def _handle_ob_query(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Query latest active strong order block from DB."""
    p = _params(node)
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    side = str(p.get("side", "both")).lower()
    min_score = int(p.get("min_score", 6))
    allow_tested_once = bool(p.get("allow_tested_once", True))

    if not storage.table_exists("order_blocks"):
        return None
    ob_cols = storage.columns("order_blocks")
    required = {"symbol", "timeframe", "side", "ob_low", "ob_high", "status", "score", "is_strong"}
    if not required.issubset(ob_cols):
        return None

    statuses = ["active"] + (["tested_once"] if allow_tested_once else [])
    placeholders = ",".join("?" for _ in statuses)
    order_col = "break_open_time" if "break_open_time" in ob_cols else "id"

    if side in ("buy", "sell"):
        db_side = {"buy": "bullish", "sell": "bearish"}[side]
        row = storage.query_one(
            f"SELECT * FROM order_blocks WHERE symbol=? AND timeframe=? AND side=? AND is_strong=1 AND score>=? AND status IN ({placeholders}) ORDER BY {order_col} DESC, id DESC LIMIT 1",
            (symbol, timeframe, db_side, min_score, *statuses),
        )
    else:
        row = storage.query_one(
            f"SELECT * FROM order_blocks WHERE symbol=? AND timeframe=? AND is_strong=1 AND score>=? AND status IN ({placeholders}) ORDER BY {order_col} DESC, id DESC LIMIT 1",
            (symbol, timeframe, min_score, *statuses),
        )
    return dict(row) if row else None


@register_node("bollinger")
def _handle_bollinger(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> dict[str, float | None] | None:
    """Bollinger Bands (upper/middle/lower)."""
    p = _params(node)
    period = int(p.get("period", 20))
    std_dev = float(p.get("std_dev", 2.0))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    cs = _closes(symbol, timeframe, period + 5)
    return bollinger_bands(cs, period, std_dev)


@register_node("macd")
def _handle_macd(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> dict[str, float | None] | None:
    """MACD line, signal line, histogram."""
    p = _params(node)
    fast = int(p.get("fast", 12))
    slow = int(p.get("slow", 26))
    signal = int(p.get("signal", 9))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    cs = _closes(symbol, timeframe, slow + signal + 5)
    return macd_func(cs, fast, slow, signal)


@register_node("value")
def _handle_value(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> Any:
    """Output a fixed value from params (for constants like thresholds, trend strings)."""
    return _params(node).get("value")


@register_node("field")
def _handle_field(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> Any:
    """Extract a named field from a dict input (e.g. bb_upper from Bollinger result)."""
    p = _params(node)
    field = str(p.get("field", ""))
    if not inputs or not field:
        return None
    val = inputs[0]
    if isinstance(val, dict):
        return val.get(field)
    return None


# ── Logic gate nodes ──


def _crossed(prev_a: float, prev_b: float, cur_a: float, cur_b: float, direction: str = "above") -> bool:
    if direction == "above":
        return prev_a <= prev_b and cur_a > cur_b
    return prev_a >= prev_b and cur_a < cur_b


def _crossed_threshold(prev_val: float | None, cur_val: float | None, threshold: float, direction: str = "above") -> bool:
    if prev_val is None or cur_val is None:
        return False
    if direction == "above":
        return prev_val < threshold and cur_val >= threshold
    return prev_val > threshold and cur_val <= threshold


@register_node("compare")
def _handle_compare(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    if len(inputs) < 2:
        return False
    a, b = inputs[0], inputs[1]
    op = str(_params(node).get("operator", ">"))
    nid = node.get("id", "?")
    symbol = ctx.get("_symbol", "?")
    tf = ctx.get("_timeframe", "?")

    # cross_above / cross_below — compare two changing values (persistent state)
    if op in ("cross_above", "cross_below"):
        state_key = f"cross:{nid}:{symbol}:{tf}"
        prev = _cross_state.get(state_key)
        _cross_state[state_key] = (a, b)
        if prev is None or a is None or b is None:
            return False
        prev_a, prev_b = prev
        if op == "cross_above":
            return _crossed(prev_a, prev_b, a, b, "above")
        return _crossed(prev_a, prev_b, a, b, "below")

    # cross_above_threshold / cross_below_threshold — value vs fixed threshold (persistent state)
    if op in ("cross_above_threshold", "cross_below_threshold"):
        state_key = f"cross_th:{nid}:{symbol}:{tf}"
        prev_val = _cross_state.get(state_key)
        _cross_state[state_key] = a
        try:
            threshold = float(b)
            cur_val = float(a) if a is not None else None
        except (TypeError, ValueError):
            return False
        return _crossed_threshold(prev_val, cur_val, threshold, "above" if op == "cross_above_threshold" else "below")

    if a is None or b is None:
        return False

    # String equality (for trend comparisons)
    if op == "==" and isinstance(a, str) and isinstance(b, str):
        return a == b
    if op == "!=" and isinstance(a, str) and isinstance(b, str):
        return a != b

    # Numeric comparisons
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if op == ">":
        return a > b
    if op == "<":
        return a < b
    if op == ">=":
        return a >= b
    if op == "<=":
        return a <= b
    if op == "==":
        return abs(a - b) < 0.0001
    if op == "!=":
        return abs(a - b) >= 0.0001
    return False


@register_node("and")
def _handle_and(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    return all(bool(v) for v in inputs if v is not None)


@register_node("or")
def _handle_or(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    return any(bool(v) for v in inputs if v is not None)


@register_node("not")
def _handle_not(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    if not inputs:
        return True
    return not bool(inputs[0])


# ── Order node ──


@register_node("price")
def _handle_price(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> float | None:
    """Return current mid/bid/ask price from tick context."""
    p = _params(node)
    value = str(p.get("value", "mid")).lower()
    bid = ctx.get("_bid")
    ask = ctx.get("_ask")
    if bid is None or ask is None:
        return None
    if value == "bid":
        return float(bid)
    if value == "ask":
        return float(ask)
    return (float(bid) + float(ask)) / 2


@register_node("ob_in_range")
def _handle_ob_in_range(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    """Check if a price is within the OB zone (ob_low <= price <= ob_high)."""
    if len(inputs) < 2:
        return False
    ob = inputs[0]
    price = inputs[1]
    if not isinstance(ob, dict) or "ob_low" not in ob or "ob_high" not in ob:
        return False
    try:
        low, high = float(ob["ob_low"]), float(ob["ob_high"])
        mid = float(price)
        return low <= mid <= high
    except (TypeError, ValueError):
        return False


_TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}


@register_node("ob_not_stale")
def _handle_ob_not_stale(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    """Check if an OB is not too old (stale) based on max_age_candles."""
    if not inputs:
        return False
    ob = inputs[0]
    if not isinstance(ob, dict):
        return False
    p = _params(node)
    max_age = int(p.get("max_age_candles", 20))
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    tf_sec = _TF_SECONDS.get(timeframe, 900)

    break_time = ob.get("break_open_time")
    if break_time is None:
        return True
    try:
        break_time = int(break_time)
    except (TypeError, ValueError):
        return True

    row = storage.query_one(
        "SELECT open_time FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT 1",
        (symbol, timeframe),
    )
    if not row:
        return True
    latest_open = int(row["open_time"])
    age_candles = (latest_open - break_time) // tf_sec
    return age_candles <= max_age


@register_node("order")
def _handle_order(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> dict[str, Any] | None:
    if not inputs or not bool(inputs[0]):
        return None
    p = _params(node)
    side = str(p.get("side", "buy")).lower()
    if side not in ("buy", "sell"):
        return None
    symbol = ctx.get("_symbol", "XAUUSD")
    timeframe = ctx.get("_timeframe", "M15")
    bid = ctx.get("_bid")
    ask = ctx.get("_ask")
    if bid is None or ask is None:
        return None

    atr_period = int(p.get("atr_period", 14))
    atr_val = _atr_value(symbol, timeframe, atr_period)
    if atr_val is None or atr_val <= 0:
        atr_val = 0.0

    sl_mult = float(p.get("sl_atr_multiplier", 1.5))
    tp_mult = float(p.get("tp_r_multiple", 2.0))
    entry_style = str(p.get("entry_style", "atr"))

    # Check for OB data in additional inputs
    ob = _get_ob_input(inputs)

    if ob and entry_style != "atr":
        ob_low = float(ob["ob_low"])
        ob_high = float(ob["ob_high"])
        ob_range = ob_high - ob_low

        if entry_style == "ob_boundary":
            # trend_ob style: entry at OB boundary, SL beyond opposite end + buffer
            buffer_ratio = float(p.get("sl_buffer_ratio", 0.30))
            buffer = ob_range * buffer_ratio
            if side == "buy":
                entry = ob_high
                sl = ob_low - buffer
            else:
                entry = ob_low
                sl = ob_high + buffer

        elif entry_style == "ob_midpoint":
            # bb_breakout/macd_cross/rsi_meanrev style: entry at midpoint
            entry = (ob_low + ob_high) / 2
            atr_buffer = max(atr_val * 0.3, ob_range * 0.1) if atr_val > 0 else ob_range * 0.1
            if side == "buy":
                sl = ob_low - atr_buffer
            else:
                sl = ob_high + atr_buffer

        else:
            # fallback to ATR-based
            entry = ask if side == "buy" else bid
            sl_distance = atr_val * sl_mult
            sl = entry - sl_distance if side == "buy" else entry + sl_distance

        risk_distance = abs(entry - sl)
        if risk_distance <= 0:
            return None
        tp = entry + risk_distance * tp_mult if side == "buy" else entry - risk_distance * tp_mult
        rr = abs(tp - entry) / risk_distance
        ob_key = f"visual_ob:{ob.get('side','?')}:{ob.get('break_open_time','?')}:{ob.get('ob_open_time','?')}"

    else:
        # ATR-based (original behavior)
        entry = ask if side == "buy" else bid
        sl_distance = atr_val * sl_mult if atr_val > 0 else 0.0

        if side == "buy":
            sl = entry - sl_distance
            tp = entry + sl_distance * tp_mult
        else:
            sl = entry + sl_distance
            tp = entry - sl_distance * tp_mult

        risk_distance = abs(entry - sl)
        if risk_distance <= 0:
            return None
        rr = abs(tp - entry) / risk_distance
        ob_key = None

    if rr < 1.5:
        return None

    return {
        "action": side,
        "entry": round(entry, 2),
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "ob_key": ob_key,
        "risk_reward": round(rr, 2),
    }


# ── Graph executor ──


def execute_graph(
    graph_def: dict[str, Any],
    bid: float,
    ask: float,
    symbol: str,
    timeframe: str,
) -> dict[str, Any] | None:
    """Execute a visual strategy graph and return a decision dict or None."""
    context: dict[str, Any] = {
        "_symbol": symbol,
        "_timeframe": timeframe,
        "_bid": bid,
        "_ask": ask,
    }
    nodes_list = graph_def.get("nodes", [])
    edges_list = graph_def.get("edges", [])
    if not nodes_list:
        return None

    nodes = {n["id"]: n for n in nodes_list}

    # Build adjacency + in-degree for topological sort
    in_degree: dict[str, int] = {}
    adj: dict[str, list[str]] = {}
    for n in nodes_list:
        nid = n["id"]
        in_degree[nid] = 0
        adj[nid] = []

    for edge in edges_list:
        src = edge.get("source", edge.get("from"))
        tgt = edge.get("target", edge.get("to"))
        if src in nodes and tgt in nodes:
            adj.setdefault(src, []).append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    # Topological sort (Kahn's algorithm)
    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    topo_order: list[str] = []
    while queue:
        nid = queue.popleft()
        topo_order.append(nid)
        for neighbor in adj.get(nid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Detect cycles (topo_order shorter than nodes)
    if len(topo_order) != len(nodes):
        return None

    # Execute in topological order
    for nid in topo_order:
        node = nodes[nid]
        ntype = node.get("type", node.get("t"))

        # Gather inputs from edges
        inputs: list[Any] = []
        for edge in edges_list:
            tgt = edge.get("target", edge.get("to"))
            if tgt == nid:
                src = edge.get("source", edge.get("from"))
                val = context.get(src)
                inputs.append(val)

        handler = _registry.get(ntype)
        if handler:
            try:
                result = handler(node, inputs, context)
                context[nid] = result
            except Exception:
                context[nid] = None

    # Check if any order node fired
    for nid in topo_order:
        node = nodes[nid]
        ntype = node.get("type", node.get("t"))
        if ntype == "order":
            result = context.get(nid)
            if isinstance(result, dict) and result.get("action"):
                return result

    return None
