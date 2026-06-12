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

    async def send(self, message: str, retries: int = 1) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        import aiohttp
        if not self._session:
            self._session = aiohttp.ClientSession()
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        for attempt in range(1 + retries):
            try:
                async with self._session.post(url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }) as resp:
                    ok = resp.status == 200
                    if not ok:
                        text = await resp.text()
                        logger.warning("Telegram API error %s (attempt %d/%d): %s", resp.status, attempt + 1, 1 + retries, text)
                    if ok:
                        return True
            except Exception as e:
                logger.error("Telegram send failed (attempt %d/%d): %s", attempt + 1, 1 + retries, e)
            if attempt < retries:
                await asyncio.sleep(1)
        return False

    def notify_trade_open(
        self,
        bot_name: str, side: str, entry: float, sl: float, tp: float, lot: float,
        symbol: str, slippage_pips: float = 0.0,
    ) -> None:
        emoji = "\U0001f7e2" if side == "buy" else "\U0001f534"
        parts = [
            f"{emoji} <b>{side.upper()} {lot} {symbol} @ {entry}</b>",
            f"Bot: {bot_name}",
            f"SL: {sl} | TP: {tp}",
        ]
        if slippage_pips:
            parts.append(f"Slippage: {slippage_pips:+.2f} pips")
        self._fire("\n".join(parts))

    def notify_trade_close(
        self,
        bot_name: str, side: str, pnl: float, reason: str, symbol: str,
        r_multiple: float = 0.0,
        commission: float = 0.0, slippage: float = 0.0, spread_cost: float = 0.0,
        net_pnl: float | None = None,
    ) -> None:
        net = net_pnl if net_pnl is not None else pnl
        emoji = "\u2705" if net > 0 else "\u274c"
        reason_clean = reason.replace("_", " ").title()
        header = f"{emoji} <b>{reason_clean}  |  {net:+.2f}</b>"
        if net_pnl is not None and abs(pnl - net) > 0.001:
            body = (
                f"Bot: {bot_name}\n"
                f"Gross PnL: <b>{pnl:+.2f}</b>\n"
                f"Commission: <b>{commission:+.2f}</b>\n"
                f"Slippage: <b>{slippage:+.2f}</b>\n"
                f"Spread Cost: <b>{spread_cost:+.2f}</b>\n"
                + "\u2500" * 13 + "\n"
                f"Net PnL: <b>{net:+.2f}</b>  |  R: {r_multiple:+.2f}"
            )
        else:
            body = (
                f"Bot: {bot_name}\n"
                f"PnL: <b>{pnl:+.2f}</b>  |  R: {r_multiple:+.2f}"
            )
        self._fire(f"{header}\n{body}")

    def notify_error(self, bot_name: str, error: str) -> None:
        self._fire(f"\U0001f6a8 <b>Bot Error</b>\nBot: {bot_name}\nError: {error}")

    def notify_risk(self, bot_name: str, alert_type: str, detail: str) -> None:
        self._fire(f"\u26a0\ufe0f <b>{alert_type}</b>\nBot: {bot_name}\n{detail}")

    def notify_health(self, alert_type: str, detail: str) -> None:
        emoji = "\U0001f534" if alert_type == "offline" else "\U0001f7e2"
        self._fire(f"{emoji} <b>System {alert_type.title()}</b>\n{detail}")

    async def test(self) -> bool:
        return await self.send("\u2705 <b>Alert System Test</b>\nYour MT5 Paper Trading alerts are working!")

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None


    def _fire(self, message: str) -> None:
        try:
            asyncio.ensure_future(self.send(message))
        except RuntimeError:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.create_task(self.send(message))
            except Exception:
                pass


alert_engine = AlertEngine()
