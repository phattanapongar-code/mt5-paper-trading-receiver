from __future__ import annotations

import math
from collections import deque
from typing import Any, Callable

from app import storage
from app.indicators import sma, rsi, atr, ema


# ── Node handler registry ──

NodeHandler = Callable[[dict[str, Any], list[Any], dict[str, Any]], Any]
_registry: dict[str, NodeHandler] = {}


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
        "compare": "Compare two values (>, <, >=, <=, ==, cross_above, cross_below)",
        "and": "Logical AND of multiple boolean inputs",
        "or": "Logical OR of multiple boolean inputs",
        "not": "Logical NOT of a boolean input",
        "order": "Generate buy/sell decision",
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


def _crossed(prev_a: float, prev_b: float, cur_a: float, cur_b: float, direction: str = "above") -> bool:
    if direction == "above":
        return prev_a <= prev_b and cur_a > cur_b
    return prev_a >= prev_b and cur_a < cur_b


@register_node("compare")
def _handle_compare(node: dict[str, Any], inputs: list[Any], ctx: dict[str, Any]) -> bool:
    if len(inputs) < 2:
        return False
    a, b = inputs[0], inputs[1]
    op = str(_params(node).get("operator", ">"))

    # cross_above / cross_below need history — fetch prev values from ctx
    if op in ("cross_above", "cross_below"):
        prev_key = f"_prev:{node.get('id','?')}"
        prev = ctx.get(prev_key)
        ctx[prev_key] = (a, b)
        if prev is None or a is None or b is None:
            return False
        prev_a, prev_b = prev
        if op == "cross_above":
            return _crossed(prev_a, prev_b, a, b, "above")
        return _crossed(prev_a, prev_b, a, b, "below")

    if a is None or b is None:
        return False
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
    atr_period = int(p.get("atr_period", 14))
    atr_val = _atr_value(symbol, timeframe, atr_period)
    if atr_val is None or atr_val <= 0:
        return None
    pip_val = _pip_value(symbol)
    sl_mult = float(p.get("sl_atr_multiplier", 1.5))
    tp_mult = float(p.get("tp_r_multiple", 2.0))

    # Get latest bid/ask from context
    bid = ctx.get("_bid")
    ask = ctx.get("_ask")
    if bid is None or ask is None:
        return None

    entry = ask if side == "buy" else bid
    sl_distance = atr_val * sl_mult

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
    if rr < 1.5:
        return None

    return {
        "action": side,
        "entry": round(entry, 2),
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "ob_key": None,
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
