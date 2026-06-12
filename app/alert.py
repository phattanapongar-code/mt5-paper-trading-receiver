from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(self) -> None:
        self.bot_token: str | None = None
        self.chat_id: str | None = None
        self.enabled: bool = False
        self._session: Any | None = None

    def configure(self, bot_token: str, chat_id: str, enabled: bool = True) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled

    async def send(self, message: str) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        try:
            import aiohttp
            if not self._session:
                self._session = aiohttp.ClientSession()
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with self._session.post(url, json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }) as resp:
                ok = resp.status == 200
                if not ok:
                    text = await resp.text()
                    logger.warning("Telegram API error %s: %s", resp.status, text)
                return ok
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    def notify_trade_open(self, bot_name: str, side: str, entry: float, sl: float, tp: float, lot: float, symbol: str) -> None:
        emoji = "\U0001f7e2" if side == "buy" else "\U0001f534"
        msg = (
            f"{emoji} <b>Trade Opened</b>\n"
            f"Bot: {bot_name}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side.upper()}\n"
            f"Entry: {entry}\n"
            f"SL: {sl}\n"
            f"TP: {tp}\n"
            f"Lot: {lot}"
        )
        asyncio.ensure_future(self.send(msg))

    def notify_trade_close(self, bot_name: str, side: str, pnl: float, reason: str, symbol: str, r_multiple: float = 0.0) -> None:
        emoji = "\u2705" if pnl > 0 else "\u274c"
        msg = (
            f"{emoji} <b>Trade Closed</b>\n"
            f"Bot: {bot_name}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side.upper()}\n"
            f"PnL: {pnl:+.2f}\n"
            f"R: {r_multiple:+.2f}\n"
            f"Reason: {reason}"
        )
        asyncio.ensure_future(self.send(msg))

    def notify_error(self, bot_name: str, error: str) -> None:
        asyncio.ensure_future(self.send(
            f"\U0001f6a8 <b>Bot Error</b>\nBot: {bot_name}\nError: {error}"
        ))

    async def test(self) -> bool:
        return await self.send("\u2705 <b>Alert System Test</b>\nYour MT5 Paper Trading alerts are working!")

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None


alert_engine = AlertEngine()
