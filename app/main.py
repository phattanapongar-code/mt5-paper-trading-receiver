from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app import storage
from app.candle_engine import CandleEngine, TIMEFRAMES
from app.config import settings
from app.models import CloseOrderRequest, HistoryImportRequest, OpenOrderRequest, ResetRequest, TickPayload
from app.market_structure import MarketStructureEngine
from app.order_blocks import OrderBlockEngine
from app.stats import StatsEngine
from app.replay import ReplayEngine
from app.multibot import service as multibot
from app.multibot.runtime import process_tick_sync

app = FastAPI(title="MT5 Paper Trading Receiver", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"},
            headers={"WWW-Authenticate": "Basic realm=\"dashboard\""},
        )
    try:
        decoded = base64.b64decode(auth.removeprefix("Basic ")).decode()
        username, password = decoded.split(":", 1)
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authorization header"},
            headers={"WWW-Authenticate": "Basic realm=\"dashboard\""},
        )
    if username != settings.dashboard_username or password != settings.dashboard_password:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"},
            headers={"WWW-Authenticate": "Basic realm=\"dashboard\""},
        )
    return await call_next(request)

storage.init_db()
storage.cleanup_old_data()
candles = CandleEngine()
structure = MarketStructureEngine()
order_blocks = OrderBlockEngine()
stats_engine = StatsEngine()
replay_engine = ReplayEngine()

latest_tick: dict[str, Any] | None = None
last_received_at: int | None = None
last_seq: int | None = None
ws_clients: set[WebSocket] = set()


async def broadcast(payload: dict[str, Any]) -> None:
    if not ws_clients:
        return
    dead: list[WebSocket] = []
    text = json.dumps(payload, ensure_ascii=False)
    for ws in list(ws_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.discard(ws)


def _paper_bot_id() -> int | None:
    bot = multibot.get_bot(1)
    return bot["id"] if bot else None


def _paper_bot_state() -> dict[str, Any]:
    bot = multibot.bot_state(1) or {}
    return bot


@app.post("/price")
async def receive_price(payload: TickPayload) -> dict[str, Any]:
    global latest_tick, last_received_at, last_seq

    now = int(time.time())
    mid = (payload.bid + payload.ask) / 2
    spread = payload.ask - payload.bid
    last_received_at = now
    last_seq = payload.seq
    latest_tick = {
        "type": payload.type,
        "symbol": payload.symbol,
        "bid": payload.bid,
        "ask": payload.ask,
        "mid": mid,
        "spread": spread,
        "timestamp": now,
        "source_timestamp": payload.timestamp,
        "seq": payload.seq,
        "received_at": now,
    }

    storage.execute(
        """
        INSERT INTO ticks(symbol, type, bid, ask, mid, spread, seq, ts, received_at, source_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payload.symbol, payload.type, payload.bid, payload.ask, mid, spread, payload.seq, now, now, payload.timestamp),
    )

    candle_result = candles.update_tick(payload.symbol, payload.bid, payload.ask, now)
    closed_timeframes = [c["timeframe"] for c in candle_result["closed"]]
    structure_refresh = structure.refresh_timeframes(payload.symbol, closed_timeframes) if closed_timeframes else {}
    order_block_refresh = order_blocks.refresh_timeframes(payload.symbol, closed_timeframes) if closed_timeframes else {}

    # All bots (including Paper Trading) are evaluated by the multibot runtime
    multibot_result = process_tick_sync(latest_tick)

    event = {
        "event": "price",
        "tick": latest_tick,
        "closed_candles": candle_result["closed"],
        "market_structure_refresh": structure_refresh,
        "order_block_refresh": order_block_refresh,
        "multibot": multibot_result,
    }
    asyncio.create_task(broadcast(event))

    return {
        "ok": True, "seq": payload.seq, "spread": spread,
        "closed_candles": len(candle_result["closed"]),
        "market_structure_refresh": structure_refresh,
        "order_block_refresh": order_block_refresh,
        "multibot": multibot_result,
    }


@app.post("/api/history/import")
def import_history(req: HistoryImportRequest) -> dict[str, Any]:
    if req.symbol != settings.symbol:
        raise HTTPException(status_code=400, detail=f"Symbol mismatch: receiver expects {settings.symbol}")
    
    if req.timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {req.timeframe}")
    
    summary = candles.import_timeframe_history(req.symbol, req.timeframe, [c.model_dump() for c in req.candles])
    market_structure = structure.rebuild_all(req.symbol)
    order_block_summary = order_blocks.rebuild_all(req.symbol)
    created_at = int(time.time())
    storage.execute(
            """
            INSERT INTO history_imports(symbol, source, timeframe, offset_seconds, imported_m1, rebuilt_m5, rebuilt_m15, rebuilt_h1, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.symbol,
                req.source,
                req.timeframe,
                req.offset_seconds,
                summary.get("imported") or summary.get("imported_m1"),
                summary["rebuilt_m5"],
                summary["rebuilt_m15"],
                summary["rebuilt_h1"],
                created_at,
            ),
        )
    return {
        "ok": True, "symbol": req.symbol, "created_at": created_at, **summary,
        "market_structure": market_structure, "order_blocks": order_block_summary,
    }


@app.get("/api/history/status")
def history_status() -> dict[str, Any]:
    counts = {
        tf: storage.query_one(
            "SELECT COUNT(*) AS count FROM candles WHERE symbol = ? AND timeframe = ? AND is_closed = 1",
            (settings.symbol, tf),
        )["count"]
        for tf in TIMEFRAMES
    }
    latest_import = storage.query_one("SELECT * FROM history_imports ORDER BY id DESC LIMIT 1")
    return {"symbol": settings.symbol, "closed_candles": counts, "latest_import": latest_import}


@app.get("/health")
def health() -> dict[str, Any]:
    now = int(time.time())
    seconds = None if last_received_at is None else now - last_received_at
    paper_bot = _paper_bot_state()
    is_enabled = bool(paper_bot.get("bot", {}).get("enabled", False)) if paper_bot else False
    return {
        "ok": True,
        "sender_online": seconds is not None and seconds <= settings.stale_tick_seconds,
        "last_received_at": last_received_at,
        "seconds_since_last_message": seconds,
        "last_seq": last_seq,
        "strategy_enabled": is_enabled,
        "websocket_clients": len(ws_clients),
    }


def _legacy_paper_state() -> dict[str, Any]:
    """Return PaperEngine-compatible state from the 'Paper Trading' bot."""
    state = _paper_bot_state()
    if not state:
        return {"balance": settings.initial_balance, "realized_pnl": 0, "unrealized_pnl": 0, "equity": settings.initial_balance, "open_position": None}
    
    bot = state.get("bot", {})
    wallet = state.get("position") or {}
    position = state.get("position")
    
    balance = float(bot.get("balance", settings.initial_balance))
    realized_pnl = float(bot.get("realized_pnl", 0))
    
    unrealized = 0.0
    if position and latest_tick:
        entry = float(position["entry"])
        side = str(position["side"])
        lot = float(position["lot"])
        exit_price = latest_tick["bid"] if side == "buy" else latest_tick["ask"]
        points = exit_price - entry if side == "buy" else entry - exit_price
        unrealized = points * lot * settings.contract_size
    
    return {
        "balance": balance,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized,
        "equity": balance + unrealized,
        "open_position": position,
    }


@app.get("/api/state")
def state() -> dict[str, Any]:
    indicator_state = {tf: candles.get_indicators(settings.symbol, tf) for tf in TIMEFRAMES}
    pending = storage.query_one("SELECT * FROM bot_pending_orders WHERE bot_id=1 AND status='pending' ORDER BY id DESC LIMIT 1")
    paper_state_obj = _legacy_paper_state()
    paper_bot = _paper_bot_state()
    is_enabled = bool(paper_bot.get("bot", {}).get("enabled", False)) if paper_bot else False
    
    return {
        "health": health(),
        "latest_tick": latest_tick,
        "paper": paper_state_obj,
        "indicators": indicator_state,
        "market_structure": {
            "M5": structure.state(settings.symbol, "M5"),
            "M15": structure.state(settings.symbol, "M15"),
            "H1": structure.state(settings.symbol, "H1"),
        },
        "order_blocks": {
            "M5": order_blocks.state(settings.symbol, "M5"),
            "M15": order_blocks.state(settings.symbol, "M15"),
            "H1": order_blocks.state(settings.symbol, "H1"),
        },
        "pending_orders": {
            "symbol": settings.symbol,
            "timeframe": "M15",
            "active": pending,
        },
        "execution": {
            "enabled": is_enabled,
            "mode": "PAPER_ONLY",
            "risk_percent": settings.trend_risk_percent,
            "contract_size": settings.contract_size,
            "lot_step": settings.lot_step,
            "min_lot": settings.min_lot,
            "max_lot": settings.max_lot,
        },
        "stats": stats_engine.summary(),
    }


@app.get("/api/ticks")
def ticks(limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    return storage.query_all("SELECT * FROM ticks ORDER BY id DESC LIMIT ?", (limit,))


@app.get("/api/candles/{timeframe}")
def get_candles(timeframe: str, limit: int = 100, closed_only: bool = False) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return candles.get_candles(settings.symbol, timeframe, max(1, min(limit, 1000)), closed_only)


@app.get("/api/indicators/{timeframe}")
def get_indicators(timeframe: str) -> dict[str, Any]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return candles.get_indicators(settings.symbol, timeframe)


@app.get("/api/swings/{timeframe}")
def get_swings(timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return structure.get_swings(settings.symbol, timeframe, max(1, min(limit, 1000)))


@app.get("/api/bos/{timeframe}")
def get_bos(timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return structure.get_bos(settings.symbol, timeframe, max(1, min(limit, 1000)))


@app.get("/api/market-structure/{timeframe}")
def get_market_structure(timeframe: str) -> dict[str, Any]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return structure.state(settings.symbol, timeframe)


@app.post("/api/market-structure/rebuild")
def rebuild_market_structure() -> dict[str, Any]:
    return {"ok": True, "symbol": settings.symbol, "market_structure": structure.rebuild_all(settings.symbol)}


@app.post("/api/order-blocks/rebuild")
def rebuild_order_blocks() -> dict[str, Any]:
    market_structure = structure.rebuild_all(settings.symbol)
    summary = order_blocks.rebuild_all(settings.symbol)
    return {"ok": True, "symbol": settings.symbol, "market_structure": market_structure, "order_blocks": summary}


@app.get("/api/order-blocks/active/{timeframe}")
def get_active_order_blocks(timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return order_blocks.get_active(settings.symbol, timeframe, max(1, min(limit, 1000)))


@app.get("/api/order-blocks/state/{timeframe}")
def get_order_block_state(timeframe: str) -> dict[str, Any]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return order_blocks.state(settings.symbol, timeframe)


@app.get("/api/order-blocks/{timeframe}")
def get_order_blocks(timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return order_blocks.get_order_blocks(settings.symbol, timeframe, max(1, min(limit, 1000)))


# ── Legacy-compatible Paper Trading endpoints (backed by bot_id=1) ──

@app.get("/api/pending-orders/state")
def get_pending_order_state() -> dict[str, Any]:
    pending = storage.query_one("SELECT * FROM bot_pending_orders WHERE bot_id=1 AND status='pending' ORDER BY id DESC LIMIT 1")
    return {
        "symbol": settings.symbol,
        "timeframe": "M15",
        "active": pending,
    }


@app.get("/api/pending-orders")
def get_pending_orders(limit: int = 50) -> list[dict[str, Any]]:
    return storage.query_all("SELECT * FROM bot_pending_orders WHERE bot_id=1 ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),))


@app.get("/api/pending-orders/rejections")
def get_pending_rejections(limit: int = 50) -> list[dict[str, Any]]:
    return storage.query_all(
        "SELECT * FROM bot_signal_logs WHERE bot_id=1 AND event_type='pending_rejected' ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 1000)),),
    )


@app.post("/api/pending-orders/evaluate")
def evaluate_pending_orders() -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    result = process_tick_sync(latest_tick)
    return {"ok": True, "multibot": result}


@app.post("/api/pending-orders/{order_id}/cancel")
def cancel_pending_order(order_id: int) -> dict[str, Any]:
    with storage.transaction() as conn:
        order = conn.execute("SELECT * FROM bot_pending_orders WHERE id=? AND bot_id=1", (order_id,)).fetchone()
        if order is None or order["status"] != "pending":
            raise HTTPException(status_code=404, detail="Pending order not found or not pending")
        conn.execute(
            "UPDATE bot_pending_orders SET status='cancelled',cancel_reason='manual_cancel',updated_at=? WHERE id=?",
            (int(time.time()), order_id),
        )
        return dict(conn.execute("SELECT * FROM bot_pending_orders WHERE id=?", (order_id,)).fetchone())


@app.post("/api/paper/open")
def open_paper(req: OpenOrderRequest) -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    bot = multibot.get_bot(1)
    if bot is None:
        raise HTTPException(status_code=500, detail="Paper Trading bot not found")
    wallet = multibot.get_wallet(1)
    if wallet is None:
        raise HTTPException(status_code=500, detail="Wallet not found")
    
    entry = latest_tick["ask"] if req.side == "buy" else latest_tick["bid"]
    now = int(time.time())
    
    with storage.transaction() as conn:
        existing = conn.execute("SELECT id FROM bot_positions WHERE bot_id=1 AND status='open' LIMIT 1").fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Only one open position is allowed")
        
        cur = conn.execute(
            """
            INSERT INTO bot_positions(bot_id,wallet_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,'open',?,?)
            """,
            (1, wallet["id"], latest_tick["symbol"], req.side, req.lot, entry, req.stop_loss, req.take_profit, now, now),
        )
        result = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (cur.lastrowid,)).fetchone())
    return result


@app.post("/api/paper/close")
def close_paper(req: CloseOrderRequest) -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    with storage.transaction() as conn:
        position = conn.execute("SELECT * FROM bot_positions WHERE bot_id=1 AND status='open' ORDER BY id DESC LIMIT 1").fetchone()
        if position is None:
            raise HTTPException(status_code=400, detail="No open position")
        p = dict(position)
        exit_price = latest_tick["bid"] if p["side"] == "buy" else latest_tick["ask"]
        direction = 1.0 if p["side"] == "buy" else -1.0
        pnl = (exit_price - float(p["entry"])) * direction * float(p["lot"]) * settings.contract_size
        risk = abs(float(p["entry"]) - float(p["stop_loss"] or p["entry"])) * float(p["lot"]) * settings.contract_size
        r_multiple = pnl / risk if risk > 0 else 0.0
        now = int(time.time())
        
        conn.execute(
            "UPDATE bot_positions SET status='closed',closed_at=?,exit_price=?,pnl=?,r_multiple=?,exit_reason=?,updated_at=? WHERE id=?",
            (now, exit_price, pnl, r_multiple, "manual" if not req.note else req.note, now, p["id"]),
        )
        wallet = conn.execute("SELECT * FROM wallets WHERE bot_id=1").fetchone()
        new_balance = float(wallet["balance"]) + pnl
        peak = max(float(wallet["peak_equity"]), new_balance)
        drawdown = ((peak - new_balance) / peak) if peak > 0 else 0.0
        max_dd = max(float(wallet["max_drawdown"]), drawdown)
        conn.execute(
            "UPDATE wallets SET balance=?,realized_pnl=realized_pnl+?,peak_equity=?,max_drawdown=?,updated_at=? WHERE bot_id=?",
            (new_balance, pnl, peak, max_dd, now, 1),
        )
        result = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (p["id"],)).fetchone())
    return result


@app.post("/api/paper/reset")
def reset_paper(req: ResetRequest | None = None) -> dict[str, Any]:
    now = int(time.time())
    new_balance = settings.initial_balance if req is None or req.balance is None else req.balance
    with storage.transaction() as conn:
        conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=1")
        conn.execute("DELETE FROM bot_positions WHERE bot_id=1")
        conn.execute(
            "UPDATE wallets SET initial_balance=?,balance=?,realized_pnl=0,max_drawdown=0,peak_equity=?,updated_at=? WHERE bot_id=?",
            (new_balance, new_balance, new_balance, now, 1),
        )
        conn.execute("UPDATE bot_runtime_state SET consecutive_losses=0,daily_realized_pnl=0,paused_reason=NULL,updated_at=? WHERE bot_id=1", (now,))
        result = dict(conn.execute("SELECT * FROM wallets WHERE bot_id=1").fetchone())
    return result


@app.get("/api/trades")
def get_trades(
    limit: int = 100,
    side: str | None = None,
    symbol: str | None = None,
    bot_id: int | None = None,
    since: int | None = None,
    until: int | None = None,
) -> list[dict[str, Any]]:
    where = "1=1"
    params: list[Any] = []
    if side and side in ("buy", "sell"):
        where += " AND side=?"
        params.append(side)
    if symbol:
        where += " AND symbol=?"
        params.append(symbol)
    if bot_id is not None:
        where += " AND bot_id=?"
        params.append(bot_id)
    if since is not None:
        where += " AND (closed_at IS NOT NULL AND closed_at>=? OR opened_at>=?)"
        params.extend([since, since])
    if until is not None:
        where += " AND (closed_at IS NOT NULL AND closed_at<=? OR opened_at<=?)"
        params.extend([until, until])
    params.append(max(1, min(limit, 1000)))
    return storage.query_all(
        f"SELECT * FROM bot_positions WHERE {where} ORDER BY id DESC LIMIT ?",
        params,
    )


@app.get("/")
def root_dashboard() -> FileResponse:
    return FileResponse("dashboard/index.html")


@app.get("/dashboard-legacy")
def dashboard() -> FileResponse:
    return FileResponse("dashboard/index.html")


@app.get("/api/strategy/status")
def strategy_status() -> dict[str, Any]:
    bot = multibot.get_bot(1)
    is_enabled = bool(bot.get("enabled", False)) if bot else False
    return {"enabled": is_enabled, "mode": "PAPER_ONLY"}


@app.post("/api/strategy/enable")
def strategy_enable() -> dict[str, Any]:
    multibot.set_bot_enabled(1, True)
    return {"enabled": True, "mode": "PAPER_ONLY"}


@app.post("/api/strategy/disable")
def strategy_disable() -> dict[str, Any]:
    multibot.set_bot_enabled(1, False)
    return {"enabled": False, "mode": "PAPER_ONLY"}


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    return stats_engine.summary()


@app.get("/api/stats/equity")
def stats_equity() -> list[tuple[int, float]]:
    return stats_engine.equity_curve()


@app.get("/api/stats/pnl-by-day")
def stats_pnl_by_day() -> list[tuple[int, float]]:
    return stats_engine.pnl_by_day()


@app.get("/api/signal-logs")
def signal_logs(limit: int = 100, bot_id: int | None = None) -> list[dict[str, Any]]:
    if bot_id is not None:
        return storage.query_all(
            "SELECT * FROM bot_signal_logs WHERE bot_id=? ORDER BY id DESC LIMIT ?",
            (bot_id, max(1, min(limit, 1000))),
        )
    return storage.query_all(
        "SELECT * FROM bot_signal_logs ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 1000)),),
    )


@app.post("/api/replay/run")
def replay_run() -> dict[str, Any]:
    return replay_engine.run(settings.symbol)


@app.get("/api/replay/latest")
def replay_latest() -> dict[str, Any] | None:
    return replay_engine.latest(settings.symbol)


@app.websocket("/ws/ticks")
async def ws_ticks(ws: WebSocket) -> None:
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)


# Multi-bot v1.1+ routes
from app.multibot.router import router as multibot_router
app.include_router(multibot_router)
