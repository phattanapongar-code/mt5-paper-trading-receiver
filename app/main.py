from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import storage
from app.candle_engine import CandleEngine, TIMEFRAMES
from app.config import settings
from app.models import CloseOrderRequest, HistoryImportRequest, OpenOrderRequest, TickPayload
from app.market_structure import MarketStructureEngine
from app.order_blocks import OrderBlockEngine
from app.replay import ReplayEngine
from app import gap_filler
from app.multibot import service as multibot
from app.multibot.runtime import process_tick_sync, hub
from app.multibot.router import router as multibot_router
from app.backtest.router import router as backtest_router
from app.alert import alert_engine
from app.trader_client import forward_health, forward_account, forward_positions, forward_open, forward_pending, forward_close, forward_close_all, forward_modify, forward_symbols_available, forward_symbols_get, forward_symbols_post, forward_history

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and graceful shutdown."""
    from app.multibot.visual_router import seed_presets
    seed_presets()
    health_task = asyncio.create_task(_health_monitor())
    report_task = asyncio.create_task(_report_scheduler())
    tg_poll_task = asyncio.create_task(_telegram_poll_loop())
    yield
    health_task.cancel()
    report_task.cancel()
    tg_poll_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    try:
        await report_task
    except asyncio.CancelledError:
        pass
    try:
        await tg_poll_task
    except asyncio.CancelledError:
        pass
    await alert_engine.close()


app = FastAPI(title="MT5 Paper Trading Receiver", version="2.5.0", lifespan=lifespan)
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
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Credentials": "true",
    }
    if not auth.startswith("Basic "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"},
            headers=cors_headers,
        )
    try:
        decoded = base64.b64decode(auth.removeprefix("Basic ")).decode()
        username, password = decoded.split(":", 1)
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authorization header"},
            headers=cors_headers,
        )
    if username != settings.dashboard_username or password != settings.dashboard_password:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"},
            headers=cors_headers,
        )
    return await call_next(request)

storage.init_db()
storage.cleanup_old_data()
candles = CandleEngine()
structure = MarketStructureEngine()
order_blocks = OrderBlockEngine()
replay_engine = ReplayEngine()

latest_tick: dict[str, Any] | None = None
last_received_at: int | None = None
last_seq: int | None = None
ws_clients: set[WebSocket] = set()

# Health alert state tracking
_was_sender_online: bool = True
_last_health_alert: float = 0.0


async def _health_monitor() -> None:
    global _was_sender_online, _last_health_alert
    while True:
        await asyncio.sleep(15)
        now = int(time.time())
        online = last_received_at is not None and (now - last_received_at) <= settings.stale_tick_seconds
        if online != _was_sender_online and (now - _last_health_alert) > 30:
            _was_sender_online = online
            _last_health_alert = now
            if online:
                alert_engine.notify_health("online", f"Sender reconnected\nLast tick: {last_received_at}")
            else:
                alert_engine.notify_health("offline", f"No ticks received for {now - last_received_at}s\nLast tick: {last_received_at}")


async def _telegram_poll_loop() -> None:
    try:
        from app.telegram_bot import poll_loop
        await poll_loop()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Telegram poll loop error")


async def _report_scheduler() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            day = datetime.now(timezone.utc).date().isoformat()
            key = f"report.sent.{day}"
            row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key=?", (key,))
            if row:
                continue
            from app.reporter import generate_daily_reports
            messages = await asyncio.to_thread(generate_daily_reports)
            for msg in messages:
                alert_engine._fire(msg, category="report")
            storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES(?,?,?)",
                            (key, "1", int(time.time())))
            if messages:
                logger.info("Daily report sent: %d bots", len(messages))
        except Exception:
            logger.exception("Report scheduler error")


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

    def tick_pipeline():
        closed_tfs: list[str] = []
        candle_result = candles.update_tick(payload.symbol, payload.bid, payload.ask, now)
        closed_tfs.extend(c["timeframe"] for c in candle_result["closed"])

        # If MT5 sent a closed M1 candle, ingest it for exact OHLC
        if payload.candle:
            c = payload.candle
            rebuild_result = candles.ingest_m1_candle(
                payload.symbol, c.open_time, c.open, c.high, c.low, c.close, c.tick_volume,
            )
            candle_result["ingested_m1"] = 1
            candle_result["rebuilt_from_m1"] = rebuild_result
            # Rebuild closes higher-timeframe candles, so refresh structure/OB
            closed_tfs.extend(tf for tf in ["M1", "M5", "M15", "H1"])

        if settings.gap_auto_fill_enabled and settings.sender_url:
            gap_filler.check_and_fill(candles, payload.symbol, now)

        struct_res = structure.refresh_timeframes(payload.symbol, closed_tfs) if closed_tfs else {}
        ob_res = order_blocks.refresh_timeframes(payload.symbol, closed_tfs) if closed_tfs else {}
        bot_result = process_tick_sync(latest_tick)
        return candle_result, struct_res, ob_res, bot_result

    try:
        candle_result, structure_refresh, order_block_refresh, multibot_result = await asyncio.to_thread(tick_pipeline)
    except Exception as exc:
        multibot_result = {"ok": False, "error": str(exc), "tick": latest_tick}
        candle_result = {"closed": []}
        structure_refresh = {}
        order_block_refresh = {}
        logger.error("tick_pipeline failed: %s", exc)
    hub.set_result(multibot_result)

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
def history_status(symbol: str = "") -> dict[str, Any]:
    sym = symbol.upper() or settings.symbol
    counts = {
        tf: storage.query_one(
            "SELECT COUNT(*) AS count FROM candles WHERE symbol = ? AND timeframe = ? AND is_closed = 1",
            (sym, tf),
        )["count"]
        for tf in TIMEFRAMES
    }
    latest_import = storage.query_one("SELECT * FROM history_imports ORDER BY id DESC LIMIT 1")
    return {"symbol": sym, "closed_candles": counts, "latest_import": latest_import}


@app.get("/health")
def health() -> dict[str, Any]:
    now = int(time.time())
    seconds = None if last_received_at is None else now - last_received_at
    bots = storage.query_all(
        "SELECT b.id,b.name,b.enabled,r.updated_at AS runtime_updated_at,r.paused_reason FROM bots b LEFT JOIN bot_runtime_state r ON r.bot_id=b.id ORDER BY b.id"
    )
    for b in bots:
        b["is_live"] = b["runtime_updated_at"] is not None and (now - b["runtime_updated_at"]) < 12
        b.pop("runtime_updated_at", None)
    return {
        "ok": True,
        "sender_online": seconds is not None and seconds <= settings.stale_tick_seconds,
        "last_received_at": last_received_at,
        "seconds_since_last_message": seconds,
        "last_seq": last_seq,
        "websocket_clients": len(ws_clients),
        "latest_tick": latest_tick,
        "bots": bots,
    }


@app.get("/symbols")
async def symbols_list() -> dict[str, list[str]]:
    rows = storage.query_all("SELECT DISTINCT symbol FROM ticks WHERE symbol IS NOT NULL ORDER BY symbol")
    symbols = [r["symbol"] for r in rows if r["symbol"]]
    if not symbols:
        symbols = settings.symbols[:]
    trader = await forward_symbols_get()
    if trader.get("ok") and trader.get("symbols"):
        for s in trader["symbols"]:
            if s not in symbols:
                symbols.append(s)
    return {"symbols": symbols}


@app.get("/api/ticks")
def ticks(limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    return storage.query_all("SELECT * FROM ticks ORDER BY id DESC LIMIT ?", (limit,))


@app.get("/api/candles/{timeframe}")
def get_candles(timeframe: str, symbol: str = "", limit: int = 100, closed_only: bool = False,
                start_time: int | None = None, end_time: int | None = None) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    # Allow much larger limit when date range is specified (for historical view)
    max_limit = 200000 if (start_time is not None or end_time is not None) else 1000
    clamped = max(1, min(limit, max_limit))
    return candles.get_candles(sym, timeframe, clamped, closed_only, start_time, end_time)


@app.get("/api/indicators/{timeframe}")
def get_indicators(timeframe: str, symbol: str = "") -> dict[str, Any]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return candles.get_indicators(sym, timeframe)


@app.get("/api/swings/{timeframe}")
def get_swings(timeframe: str, symbol: str = "", limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return structure.get_swings(sym, timeframe, max(1, min(limit, 1000)))


@app.get("/api/bos/{timeframe}")
def get_bos(timeframe: str, symbol: str = "", limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return structure.get_bos(sym, timeframe, max(1, min(limit, 1000)))


@app.get("/api/market-structure/{timeframe}")
def get_market_structure(timeframe: str, symbol: str = "") -> dict[str, Any]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return structure.state(sym, timeframe)


@app.post("/api/market-structure/rebuild")
def rebuild_market_structure(symbol: str = "") -> dict[str, Any]:
    sym = symbol.upper() or settings.symbol
    return {"ok": True, "symbol": sym, "market_structure": structure.rebuild_all(sym)}


@app.post("/api/order-blocks/rebuild")
def rebuild_order_blocks(symbol: str = "") -> dict[str, Any]:
    sym = symbol.upper() or settings.symbol
    market_structure = structure.rebuild_all(sym)
    summary = order_blocks.rebuild_all(sym)
    return {"ok": True, "symbol": sym, "market_structure": market_structure, "order_blocks": summary}


@app.get("/api/order-blocks/active/{timeframe}")
def get_active_order_blocks(timeframe: str, symbol: str = "", limit: int = 50) -> list[dict[str, Any]]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return order_blocks.get_active(sym, timeframe, max(1, min(limit, 1000)))


@app.get("/api/order-blocks/state/{timeframe}")
def get_order_block_state(timeframe: str, symbol: str = "") -> dict[str, Any]:
    timeframe = timeframe.upper()
    sym = symbol.upper() or settings.symbol
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe. Use one of {list(TIMEFRAMES)}")
    return order_blocks.state(sym, timeframe)


# ── Pending Orders ──

@app.get("/api/pending-orders")
def get_pending_orders(limit: int = 50, bot_id: int | None = None) -> list[dict[str, Any]]:
    if bot_id is not None:
        return storage.query_all("SELECT * FROM bot_pending_orders WHERE bot_id=? ORDER BY id DESC LIMIT ?", (bot_id, max(1, min(limit, 1000))))
    return storage.query_all("SELECT * FROM bot_pending_orders ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),))


@app.get("/api/pending-orders/rejections")
def get_pending_rejections(limit: int = 50, bot_id: int | None = None) -> list[dict[str, Any]]:
    clamped = max(1, min(limit, 1000))
    try:
        if bot_id is not None:
            return storage.query_all(
                "SELECT sl.*, b.name AS bot_name FROM bot_signal_logs sl LEFT JOIN bots b ON b.id=sl.bot_id WHERE sl.bot_id=? AND sl.event_type='pending_rejected' ORDER BY sl.id DESC LIMIT ?",
                (bot_id, clamped),
            )
        return storage.query_all(
            "SELECT sl.*, b.name AS bot_name FROM bot_signal_logs sl LEFT JOIN bots b ON b.id=sl.bot_id WHERE sl.event_type='pending_rejected' ORDER BY sl.id DESC LIMIT ?",
            (clamped,),
        )
    except Exception as e:
        logger.error("Failed to fetch pending rejections: %s", e)
        return []


@app.post("/api/pending-orders/evaluate")
def evaluate_pending_orders() -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    result = process_tick_sync(latest_tick)
    return {"ok": True, "multibot": result}


@app.post("/api/pending-orders/{order_id}/cancel")
def cancel_pending_order(order_id: int, bot_id: int | None = None) -> dict[str, Any]:
    with storage.transaction() as conn:
        if bot_id is not None:
            order = conn.execute("SELECT * FROM bot_pending_orders WHERE id=? AND bot_id=?", (order_id, bot_id)).fetchone()
        else:
            order = conn.execute("SELECT * FROM bot_pending_orders WHERE id=?", (order_id,)).fetchone()
        if order is None or order["status"] != "pending":
            raise HTTPException(status_code=404, detail="Pending order not found or not pending")
        conn.execute(
            "UPDATE bot_pending_orders SET status='cancelled',cancel_reason='manual_cancel',updated_at=? WHERE id=?",
            (int(time.time()), order_id),
        )
        bot_row = conn.execute("SELECT name FROM bots WHERE id=?", (order["bot_id"],)).fetchone()
        alert_engine.notify_pending_cancelled(
            str(bot_row["name"]) if bot_row else "?",
            str(order["symbol"]), str(order["side"]), "manual_cancel", float(order["entry"]),
            bot_id=order["bot_id"],
        )
        return dict(conn.execute("SELECT * FROM bot_pending_orders WHERE id=?", (order_id,)).fetchone())


# ── Per-bot manual open/close ──

@app.post("/api/bots/{bot_id}/open")
def bot_open_position(bot_id: int, req: OpenOrderRequest) -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    try:
        result = multibot.open_position(bot_id, req.side, req.lot, req.stop_loss, req.take_profit, latest_tick)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="bot not found")
    return result


@app.post("/api/bots/{bot_id}/close")
def bot_close_position(bot_id: int, req: CloseOrderRequest) -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    try:
        result = multibot.close_position(bot_id, latest_tick, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="bot not found")
    return result


# ── Per-bot stats ──

@app.get("/api/bots/{bot_id}/stats")
def bot_stats(bot_id: int):
    return multibot.bot_stats_summary(bot_id)


@app.get("/api/bots/{bot_id}/stats/equity")
def bot_stats_equity(bot_id: int):
    return multibot.bot_equity_curve(bot_id)


@app.get("/api/bots/{bot_id}/stats/pnl-by-day")
def bot_stats_pnl_by_day(bot_id: int):
    return multibot.bot_pnl_by_day(bot_id)


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
        f"SELECT *, exit_price AS \"exit\" FROM bot_positions WHERE {where} ORDER BY id DESC LIMIT ?",
        params,
    )


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
def replay_run(symbol: str = "") -> dict[str, Any]:
    sym = symbol.upper() or settings.symbol
    return replay_engine.run(sym)


@app.get("/api/replay/latest")
def replay_latest(symbol: str = "") -> dict[str, Any] | None:
    sym = symbol.upper() or settings.symbol
    return replay_engine.latest(sym)


@app.get("/api/symbols")
async def get_symbols() -> dict[str, list[str]]:
    rows = storage.query_all(
        "SELECT DISTINCT symbol FROM candles WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"
    )
    symbols = []
    if rows:
        symbols = [r["symbol"] for r in rows]
    if not symbols:
        rows = storage.query_all(
            "SELECT DISTINCT symbol FROM ticks WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"
        )
        if rows:
            symbols = [r["symbol"] for r in rows]
    if not symbols:
        symbols = ["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD",
                    "USDCAD", "USDJPY", "AUDUSD", "SPX500", "NAS100"]
    trader = await forward_symbols_get()
    if trader.get("ok") and trader.get("symbols"):
        for s in trader["symbols"]:
            if s not in symbols:
                symbols.append(s)
    return {"symbols": symbols}


@app.websocket("/ws/ticks")
async def ws_ticks(ws: WebSocket) -> None:
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)


# ── Real Trading Proxy (→ trader.py :5051) ──

@app.get("/api/trader/health")
async def api_trader_health():
    return await forward_health()


@app.get("/api/trader/account")
async def api_trader_account():
    return await forward_account()


@app.get("/api/trader/positions")
async def api_trader_positions(symbol: str = ""):
    return await forward_positions(symbol)


@app.post("/api/trader/open")
async def api_trader_open(request: Request):
    body = await request.json()
    return await forward_open(body)


@app.post("/api/trader/pending")
async def api_trader_pending(request: Request):
    body = await request.json()
    return await forward_pending(body)


@app.post("/api/trader/close")
async def api_trader_close(request: Request):
    body = await request.json()
    return await forward_close(body)


@app.post("/api/trader/close_all")
async def api_trader_close_all(request: Request):
    body = await request.json()
    return await forward_close_all(body)


@app.post("/api/trader/modify")
async def api_trader_modify(request: Request):
    body = await request.json()
    return await forward_modify(body)


@app.get("/api/trader/symbols")
async def api_trader_symbols():
    return await forward_symbols_get()


@app.get("/api/trader/symbols/available")
async def api_trader_symbols_available():
    return await forward_symbols_available()


@app.post("/api/trader/symbols")
async def api_trader_symbols_update(request: Request):
    body = await request.json()
    return await forward_symbols_post(body.get("symbols", []))


@app.get("/api/trader/history")
async def api_trader_history(limit: int = 100, days: int = 30):
    return await forward_history(limit, days)


# Receive webhook callbacks from trader.py (order_filled events)
@app.post("/trader/webhook")
async def trader_webhook(request: Request):
    body = await request.json()
    event = body.get("event", "?")
    logger.info("Trader webhook received: event=%s", event)

    if event == "order_filled":
        logger.info("ORDER_FILLED | ticket=%s symbol=%s type=%s volume=%s price=%s sl=%s tp=%s",
            body.get("ticket"), body.get("symbol"), body.get("type"),
            body.get("volume"), body.get("open_price"), body.get("sl"), body.get("tp"))
    elif event == "order_pending":
        logger.info("ORDER_PENDING | ticket=%s symbol=%s type=%s volume=%s price=%s",
            body.get("ticket"), body.get("symbol"), body.get("type"),
            body.get("volume"), body.get("price"))
    elif event == "position_closed":
        logger.info("POSITION_CLOSED | ticket=%s symbol=%s type=%s volume=%s close_price=%s profit=%s commission=%s",
            body.get("ticket"), body.get("symbol"), body.get("type"),
            body.get("volume"), body.get("close_price"), body.get("profit"), body.get("commission"))
    elif event == "position_modified":
        logger.info("POSITION_MODIFIED | ticket=%s sl=%s tp=%s",
            body.get("ticket"), body.get("sl"), body.get("tp"))
    elif event == "all_positions_closed":
        logger.info("ALL_POSITIONS_CLOSED | count=%s", body.get("count"))
    else:
        logger.info("UNKNOWN_EVENT | body=%s", body)

    return {"ok": True}


# Multi-bot v1.1+ routes
app.include_router(multibot_router)

# Backtest router
app.include_router(backtest_router)

# Visual strategy builder router
from app.multibot.visual_router import router as visual_router
app.include_router(visual_router)

# Ensure at least one bot exists (seeds "Paper Trading" bot if DB is empty)
multibot.ensure_default_bot()

# ── Alert Config Endpoints ──

# Load saved alert config from DB into engine
_token_row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.bot_token'")
_chat_row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.chat_id'")
_enabled_row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.enabled'")
_cats_row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.enabled_categories'")
_cats = json.loads(_cats_row["value"]) if _cats_row else None
if _token_row and _chat_row:
    alert_engine.configure(
        bot_token=_token_row["value"],
        chat_id=_chat_row["value"],
        enabled=(_enabled_row["value"] if _enabled_row else "0") == "1",
        enabled_categories=_cats,
    )
    alert_engine.load_bot_chat_ids()


@app.get("/api/alerts/config")
def get_alert_config() -> dict[str, Any]:
    token = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.bot_token'")
    chat = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.chat_id'")
    enabled = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.enabled'")
    cats_row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.enabled_categories'")
    cats = json.loads(cats_row["value"]) if cats_row else None
    return {
        "bot_token": token["value"] if token else "",
        "chat_id": chat["value"] if chat else "",
        "enabled": (enabled["value"] if enabled else "0") == "1",
        "enabled_categories": cats if cats else ["trade", "risk", "error", "health", "pending", "trail", "report"],
    }


class AlertConfigRequest(BaseModel):
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False
    enabled_categories: list[str] | None = None


@app.post("/api/alerts/config")
def save_alert_config(req: AlertConfigRequest) -> dict[str, Any]:
    now = int(time.time())
    storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES('alert.bot_token',?,?)", (req.bot_token, now))
    storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES('alert.chat_id',?,?)", (req.chat_id, now))
    storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES('alert.enabled',?,?)", ("1" if req.enabled else "0", now))
    cats = req.enabled_categories or ["trade", "risk", "error", "health", "pending", "trail", "report"]
    storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES('alert.enabled_categories',?,?)", (json.dumps(cats), now))
    alert_engine.configure(req.bot_token, req.chat_id, req.enabled, cats)
    return {"ok": True}


@app.post("/api/alerts/test")
async def test_alert() -> dict[str, Any]:
    ok = await alert_engine.test()
    return {"ok": ok, "message": "Test alert sent" if ok else "Alert sending failed"}


@app.get("/api/bots/{bot_id}/alert-chat")
def get_bot_alert_chat(bot_id: int) -> dict[str, Any]:
    row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key=?", (f"alert.chat_id.bot_{bot_id}",))
    return {"bot_id": bot_id, "chat_id": row["value"] if row else ""}


class BotAlertChatRequest(BaseModel):
    chat_id: str = ""


@app.put("/api/bots/{bot_id}/alert-chat")
def set_bot_alert_chat(bot_id: int, req: BotAlertChatRequest) -> dict[str, Any]:
    now = int(time.time())
    if req.chat_id:
        storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES(?,?,?)",
                        (f"alert.chat_id.bot_{bot_id}", req.chat_id, now))
    else:
        storage.execute("DELETE FROM multibot_runtime_settings WHERE key=?", (f"alert.chat_id.bot_{bot_id}",))
    alert_engine.configure_bot(bot_id, req.chat_id)
    return {"ok": True, "bot_id": bot_id, "chat_id": req.chat_id}
