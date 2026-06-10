from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import storage
from app.candle_engine import CandleEngine, TIMEFRAMES
from app.config import settings
from app.models import CloseOrderRequest, HistoryImportRequest, OpenOrderRequest, ResetRequest, TickPayload
from app.market_structure import MarketStructureEngine
from app.order_blocks import OrderBlockEngine
from app.paper_engine import PaperEngine

app = FastAPI(title="MT5 Paper Trading Receiver", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage.init_db()
candles = CandleEngine()
paper = PaperEngine()
structure = MarketStructureEngine()
order_blocks = OrderBlockEngine()

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
        # Use receiver arrival time for live candle bucketing. Keep the MT5
        # timestamp separately for diagnostics because broker time may be offset.
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
    closed_position = paper.on_tick(payload.bid, payload.ask)

    event = {
        "event": "price",
        "tick": latest_tick,
        "closed_candles": candle_result["closed"],
        "closed_position": closed_position,
        "market_structure_refresh": structure_refresh,
        "order_block_refresh": order_block_refresh,
    }
    asyncio.create_task(broadcast(event))

    return {
        "ok": True, "seq": payload.seq, "spread": spread,
        "closed_candles": len(candle_result["closed"]),
        "market_structure_refresh": structure_refresh,
        "order_block_refresh": order_block_refresh,
    }


@app.post("/api/history/import/m1")
def import_m1_history(req: HistoryImportRequest) -> dict[str, Any]:
    if req.symbol != settings.symbol:
        raise HTTPException(status_code=400, detail=f"Symbol mismatch: receiver expects {settings.symbol}")
    summary = candles.import_m1_history(req.symbol, [c.model_dump() for c in req.candles])
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
            summary["imported_m1"],
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
    return {
        "ok": True,
        "sender_online": seconds is not None and seconds <= settings.stale_tick_seconds,
        "last_received_at": last_received_at,
        "seconds_since_last_message": seconds,
        "last_seq": last_seq,
        "strategy_enabled": settings.strategy_enabled,
        "websocket_clients": len(ws_clients),
    }


@app.get("/api/state")
def state() -> dict[str, Any]:
    paper_state = paper.state(
        bid=latest_tick["bid"] if latest_tick else None,
        ask=latest_tick["ask"] if latest_tick else None,
    )
    indicator_state = {tf: candles.get_indicators(settings.symbol, tf) for tf in TIMEFRAMES}
    return {
        "health": health(),
        "latest_tick": latest_tick,
        "paper": paper_state,
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
    # Rebuild market structure first so OB candidates always derive from the
    # latest closed-candle swings and BOS events.
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


@app.post("/api/paper/open")
def open_paper(req: OpenOrderRequest) -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    try:
        return paper.open_position(
            symbol=latest_tick["symbol"], side=req.side, lot=req.lot,
            bid=latest_tick["bid"], ask=latest_tick["ask"],
            stop_loss=req.stop_loss, take_profit=req.take_profit, note=req.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/paper/close")
def close_paper(req: CloseOrderRequest) -> dict[str, Any]:
    if latest_tick is None:
        raise HTTPException(status_code=400, detail="No tick received yet")
    try:
        return paper.close_position(latest_tick["bid"], latest_tick["ask"], req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/paper/reset")
def reset_paper(req: ResetRequest | None = None) -> dict[str, Any]:
    return paper.reset(None if req is None else req.balance)


@app.get("/api/trades")
def get_trades(limit: int = 100) -> list[dict[str, Any]]:
    return paper.trades(max(1, min(limit, 1000)))


@app.websocket("/ws/ticks")
async def ws_ticks(ws: WebSocket) -> None:
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)
