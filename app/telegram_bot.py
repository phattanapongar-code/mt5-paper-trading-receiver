from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app import storage
from app.alert import alert_engine

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3

_COMMANDS = {
    "/help": "Show this help message",
    "/status": "Show bot status summary",
    "/balance": "Show wallet balances",
    "/positions": "Show open positions",
    "/report": "Request a fresh daily report",
    "/pause": "Disable all bots (pause trading)",
    "/resume": "Enable all bots (resume trading)",
}


def _chat_ids() -> set[str]:
    ids = set()
    row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.chat_id'")
    if row and row["value"]:
        ids.add(str(row["value"]))
    rows = storage.query_all("SELECT key, value FROM multibot_runtime_settings WHERE key LIKE 'alert.chat_id.bot_%'") or []
    for r in rows:
        if r["value"]:
            ids.add(str(r["value"]))
    return ids


def _check_auth(chat_id: str) -> bool:
    return chat_id in _chat_ids()


async def poll_loop() -> None:
    row = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='alert.bot_token'")
    if not row or not row["value"]:
        logger.info("Telegram bot: no token configured, skipping poll")
        return
    token = str(row["value"])

    offset_row = storage.query_one("SELECT key FROM multibot_runtime_settings WHERE key='telegram.poll_offset'")
    offset = 0
    try:
        from app.alert import _escape
    except ImportError:
        def _escape(s: str) -> str:
            return s

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=10&offset={offset}"
            import httpx
            async with httpx.AsyncClient(timeout=15) as cl:
                resp = await cl.get(url)
            data = resp.json()
            if not data.get("ok"):
                continue
            for update in data.get("result", []):
                update_id = int(update["update_id"])
                if update_id >= offset:
                    offset = update_id + 1
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                if not _check_auth(chat_id):
                    await _reply(token, chat_id, "\u26a0\ufe0f Unauthorized. This bot is private.")
                    continue
                await _handle_command(token, chat_id, text)

            storage.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key,value,updated_at) VALUES('telegram.poll_offset',?,?)",
                            (str(offset), int(time.time())))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram poll error")


async def _reply(token: str, chat_id: str, text: str) -> None:
    import httpx
    from app.alert import _escape
    async with httpx.AsyncClient(timeout=10) as cl:
        await cl.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": _escape(text), "parse_mode": "HTML"},
        )


async def _handle_command(token: str, chat_id: str, text: str) -> None:
    parts = text.lower().split()
    cmd = parts[0]
    args = parts[1:]

    if cmd == "/help":
        lines = ["\U0001f916 <b>Available Commands</b>"] + [f"{c} \u2014 {d}" for c, d in _COMMANDS.items()]
        await _reply(token, chat_id, "\n".join(lines))

    elif cmd == "/status":
        bots = storage.query_all("SELECT id, name, enabled FROM bots ORDER BY id") or []
        lines = ["\U0001f4ca <b>Bot Status</b>"]
        for b in bots:
            color = "\U0001f7e2" if b["enabled"] else "\U0001f534"
            lines.append(f"{color} {b['name']} (ID {b['id']})")
        await _reply(token, chat_id, "\n".join(lines))

    elif cmd == "/balance":
        bots = storage.query_all("SELECT id, name FROM bots ORDER BY id") or []
        lines = ["\U0001f4b0 <b>Balances</b>"]
        for b in bots:
            w = storage.query_one("SELECT balance, equity FROM wallets WHERE bot_id=?", (b["id"],))
            if w:
                lines.append(f"{b['name']}: ${float(w['balance']):.2f} (eq: ${float(w['equity']):.2f})")
            else:
                lines.append(f"{b['name']}: N/A")
        await _reply(token, chat_id, "\n".join(lines))

    elif cmd == "/positions":
        positions = storage.query_all(
            "SELECT bp.id, bp.bot_id, bp.symbol, bp.side, bp.volume, bp.open_price, b.name "
            "FROM bot_positions bp JOIN bots b ON bp.bot_id=b.id "
            "WHERE bp.status='open' ORDER BY bp.id"
        ) or []
        lines = ["\U0001f4f0 <b>Open Positions</b>"]
        for p in positions:
            side_icon = "\U0001f7e2" if p["side"] == "buy" else "\U0001f534"
            lines.append(f"{side_icon} #{p['id']} {p['name']}: {p['symbol']} {p['side'].upper()} {float(p['volume']):.2f} @ {float(p['open_price']):.2f}")
        if not positions:
            lines.append("No open positions.")
        await _reply(token, chat_id, "\n".join(lines))

    elif cmd == "/report":
        from app.reporter import generate_daily_reports
        messages = await asyncio.to_thread(generate_daily_reports)
        if messages:
            for msg in messages:
                await _reply(token, chat_id, msg)
        else:
            await _reply(token, chat_id, "No trades today.")

    elif cmd == "/pause":
        storage.execute("UPDATE bots SET enabled=0 WHERE enabled=1")
        await _reply(token, chat_id, "\u23f8\ufe0f All bots paused.")

    elif cmd == "/resume":
        storage.execute("UPDATE bots SET enabled=1 WHERE enabled=0")
        await _reply(token, chat_id, "\u25b6\ufe0f All bots resumed.")

    else:
        await _reply(token, chat_id, f"Unknown command: {cmd}. Type /help for available commands.")
