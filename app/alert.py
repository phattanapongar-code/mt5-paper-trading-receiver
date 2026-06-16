from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

import aiohttp

logger = logging.getLogger(__name__)

_alert_loop: asyncio.AbstractEventLoop | None = None
_alert_loop_lock = threading.Lock()


def _get_alert_loop() -> asyncio.AbstractEventLoop:
    global _alert_loop
    if _alert_loop is None or _alert_loop.is_closed():
        with _alert_loop_lock:
            if _alert_loop is None or _alert_loop.is_closed():
                _alert_loop = asyncio.new_event_loop()
                t = threading.Thread(target=_alert_loop.run_forever, daemon=True)
                t.start()
    return _alert_loop


class AlertEngine:
    def __init__(self) -> None:
        self.bot_token: str | None = None
        self.chat_id: str | None = None
        self.enabled: bool = False
        self._enabled_categories: set[str] = {"trade", "risk", "error", "health", "pending", "trail"}
        self._last_sent: float = 0.0
        self._rate_limit_until: float = 0.0
        self._queue: asyncio.Queue | None = None
        self._worker_task: asyncio.Task | None = None

    def configure(self, bot_token: str, chat_id: str, enabled: bool = True, enabled_categories: list[str] | None = None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        if enabled_categories is not None:
            self._enabled_categories = set(enabled_categories)

    def _ensure_worker(self) -> None:
        if self._queue is not None:
            return
        loop = _get_alert_loop()
        self._queue = asyncio.Queue(maxsize=200)
        self._worker_task = loop.create_task(self._queue_worker())

    async def _queue_worker(self) -> None:
        while True:
            try:
                message = await self._queue.get()
                await self._send_with_ratelimit(message)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Alert queue worker error")

    async def _send_with_ratelimit(self, message: str) -> bool:
        now = time.time()
        if now < self._rate_limit_until:
            await asyncio.sleep(self._rate_limit_until - now)
        wait = max(0, self._last_sent + 1.0 - time.time())
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_sent = time.time()
        return await self.send(message)

    async def send(self, message: str, retries: int = 1) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        for attempt in range(1 + retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    }) as resp:
                        ok = resp.status == 200
                        if not ok:
                            text = await resp.text()
                            logger.warning("Telegram API error %s (attempt %d/%d): %s", resp.status, attempt + 1, 1 + retries, text)
                            if resp.status == 429:
                                try:
                                    body = json.loads(text)
                                    retry_after = body.get("parameters", {}).get("retry_after", 5)
                                    self._rate_limit_until = time.time() + retry_after
                                except Exception:
                                    self._rate_limit_until = time.time() + 5
                        if ok:
                            return True
            except Exception as e:
                logger.error("Telegram send failed (attempt %d/%d): %s", attempt + 1, 1 + retries, e)
            if attempt < retries:
                await asyncio.sleep(1)
        return False

    def _fire(self, message: str, category: str = "trade") -> None:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return
        if category not in self._enabled_categories:
            return
        self._ensure_worker()
        loop = _get_alert_loop()
        asyncio.run_coroutine_threadsafe(self._queue.put(message), loop)

    # ── Trade Alerts ──

    def notify_trade_open(
        self,
        bot_name: str, side: str, entry: float, sl: float, tp: float, lot: float,
        symbol: str, slippage_pips: float = 0.0, source: str = "auto",
    ) -> None:
        emoji = "\U0001f7e2" if side == "buy" else "\U0001f534"
        tag = "" if source == "auto" else " [Manual]"
        parts = [
            f"{emoji} <b>{side.upper()} {lot} {symbol} @ {entry}</b>{tag}",
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
        net_pnl: float | None = None, source: str = "auto",
    ) -> None:
        net = net_pnl if net_pnl is not None else pnl
        emoji = "\u2705" if net > 0 else "\u274c"
        reason_clean = reason.replace("_", " ").title()
        tag = "" if source == "auto" else " [Manual]"
        header = f"{emoji} <b>{reason_clean}  |  {net:+.2f}</b>{tag}"
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

    # ── Pending Order Alerts ──

    def notify_pending_created(
        self,
        bot_name: str, symbol: str, side: str, entry: float, sl: float, tp: float,
        lot: float, expiry: int, strategy: str,
    ) -> None:
        emoji = "\U0001f7e2" if side == "buy" else "\U0001f534"
        from datetime import datetime
        expiry_str = datetime.fromtimestamp(expiry).strftime("%H:%M")
        self._fire(
            f"{emoji} <b>Pending {side.upper()} {lot} {symbol} @ {entry}</b>\n"
            f"Bot: {bot_name}\n"
            f"SL: {sl} | TP: {tp}\n"
            f"Strategy: {strategy} | Expiry: ~{expiry_str}",
            category="pending",
        )

    def notify_pending_cancelled(
        self,
        bot_name: str, symbol: str, side: str, reason: str, entry: float,
    ) -> None:
        reason_clean = reason.replace("_", " ").title()
        self._fire(
            f"\u274c <b>Pending Cancelled</b>\n"
            f"Bot: {bot_name}\n"
            f"{side.upper()} {symbol} @ {entry}\n"
            f"Reason: {reason_clean}",
            category="pending",
        )

    # ── SL/Trail Alerts ──

    def notify_trail_update(
        self,
        bot_name: str, symbol: str, side: str, old_sl: float, new_sl: float, reason: str,
    ) -> None:
        reason_clean = reason.title()
        self._fire(
            f"\U0001f6a1 <b>SL Updated ({reason_clean})</b>\n"
            f"Bot: {bot_name}\n"
            f"{side.upper()} {symbol}\n"
            f"SL: {old_sl} \u2192 {new_sl}",
            category="trail",
        )

    # ── Drawdown Alert ──

    def notify_drawdown(
        self,
        bot_name: str, drawdown_pct: float, balance: float, limit_pct: float,
    ) -> None:
        self._fire(
            f"\u26a0\ufe0f <b>Drawdown Alert</b>\n"
            f"Bot: {bot_name}\n"
            f"Drawdown: {drawdown_pct:.1f}% (limit: {limit_pct:.0f}%)\n"
            f"Balance: {balance:.2f}",
            category="risk",
        )

    # ── Error / Risk / Health ──

    def notify_error(self, bot_name: str, error: str) -> None:
        self._fire(f"\U0001f6a8 <b>Bot Error</b>\nBot: {bot_name}\nError: {error}")

    def notify_risk(self, bot_name: str, alert_type: str, detail: str) -> None:
        self._fire(f"\u26a0\ufe0f <b>{alert_type}</b>\nBot: {bot_name}\n{detail}")

    def notify_health(self, alert_type: str, detail: str) -> None:
        emoji = "\U0001f534" if alert_type == "offline" else "\U0001f7e2"
        self._fire(f"{emoji} <b>System {alert_type.title()}</b>\n{detail}", category="health")

    async def test(self) -> bool:
        return await self.send("\u2705 <b>Alert System Test</b>\nYour MT5 Paper Trading alerts are working!")

    async def close(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass


alert_engine = AlertEngine()
