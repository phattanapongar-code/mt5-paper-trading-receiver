from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"http://{settings.trade_host}:{settings.trade_port}"
HEADERS = {
    "X-API-Key": settings.trade_api_key,
    "Content-Type": "application/json",
}
TIMEOUT = 10.0


def _headers() -> dict[str, str]:
    return HEADERS


async def _get(path: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"{BASE_URL}{path}", headers=_headers())
            if r.status_code >= 500:
                return {"ok": False, "error": f"Trader server error: {r.status_code}"}
            return r.json()
    except httpx.ConnectError:
        return {"ok": False, "error": "Trader server not reachable (port 5051)"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Trader server timeout"}
    except Exception as e:
        logger.exception("trader_client GET %s failed", path)
        return {"ok": False, "error": str(e)}


async def _post(path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(f"{BASE_URL}{path}", json=data or {}, headers=_headers())
            if r.status_code >= 500:
                return {"ok": False, "error": f"Trader server error: {r.status_code}"}
            return r.json()
    except httpx.ConnectError:
        return {"ok": False, "error": "Trader server not reachable (port 5051)"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Trader server timeout"}
    except Exception as e:
        logger.exception("trader_client POST %s failed", path)
        return {"ok": False, "error": str(e)}


async def forward_health() -> dict[str, Any]:
    return await _get("/health")


async def forward_account() -> dict[str, Any]:
    return await _get("/trade/account")


async def forward_positions(symbol: str = "") -> dict[str, Any]:
    path = "/trade/positions"
    if symbol:
        path += f"?symbol={symbol}"
    return await _get(path)


async def forward_open(data: dict[str, Any]) -> dict[str, Any]:
    return await _post("/trade/open", data)


async def forward_pending(data: dict[str, Any]) -> dict[str, Any]:
    return await _post("/trade/pending", data)


async def forward_close(data: dict[str, Any]) -> dict[str, Any]:
    return await _post("/trade/close", data)


async def forward_close_all(data: dict[str, Any]) -> dict[str, Any]:
    return await _post("/trade/close_all", data)


async def forward_modify(data: dict[str, Any]) -> dict[str, Any]:
    return await _post("/trade/modify", data)


async def forward_symbols_available() -> dict[str, Any]:
    return await _get("/trader/symbols/available")


async def forward_symbols_get() -> dict[str, Any]:
    return await _get("/trader/symbols")


async def forward_history(limit: int = 100, days: int = 30) -> dict[str, Any]:
    return await _get(f"/trade/history?limit={limit}&days={days}")


async def forward_symbols_post(symbols: list[str]) -> dict[str, Any]:
    return await _post("/trader/symbols", {"symbols": symbols})
