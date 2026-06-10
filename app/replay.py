from __future__ import annotations

import time
from typing import Any

from app import storage
from app.config import settings


class ReplayEngine:
    """Research preview replay using stored strong M15 order blocks and M1 bars.

    This is intentionally labelled preview: it is useful for comparing rules,
    but it is not a tick-perfect broker execution simulator.
    """

    def run(self, symbol: str) -> dict[str, Any]:
        obs = storage.query_all(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = 'M15' AND is_strong = 1
            ORDER BY break_open_time ASC, id ASC
            """,
            (symbol,),
        )
        results: list[dict[str, Any]] = []
        for ob in obs:
            result = self._simulate_ob(symbol, ob)
            if result is not None:
                results.append(result)
        wins = len([r for r in results if r["result"] == "tp"])
        losses = len([r for r in results if r["result"] == "sl"])
        unresolved = len([r for r in results if r["result"] in {"expired", "open"}])
        payload = {
            "mode": "RESEARCH_PREVIEW_NOT_TICK_PERFECT",
            "symbol": symbol,
            "created_at": int(time.time()),
            "strong_ob_candidates": len(obs),
            "simulated": len(results),
            "wins": wins,
            "losses": losses,
            "unresolved": unresolved,
            "win_rate_resolved": wins / (wins + losses) if wins + losses else 0.0,
            "net_r": sum(float(r["r_multiple"]) for r in results),
            "results": results[-100:],
        }
        storage.execute(
            "INSERT INTO replay_runs(symbol, payload, created_at) VALUES (?, ?, ?)",
            (symbol, __import__('json').dumps(payload, ensure_ascii=False), payload["created_at"]),
        )
        return payload

    def latest(self, symbol: str) -> dict[str, Any] | None:
        row = storage.query_one("SELECT * FROM replay_runs WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,))
        if row is None:
            return None
        return __import__('json').loads(row["payload"])

    def _simulate_ob(self, symbol: str, ob: dict[str, Any]) -> dict[str, Any] | None:
        low = float(ob["ob_low"])
        high = float(ob["ob_high"])
        width = high - low
        if width <= 0:
            return None
        entry = (low + high) / 2.0
        buffer = width * float(settings.pending_sl_buffer_ratio)
        if ob["side"] == "bullish":
            side = "buy"
            sl = low - buffer
            risk = entry - sl
            tp = entry + risk * float(settings.pending_tp_r_multiple)
        else:
            side = "sell"
            sl = high + buffer
            risk = sl - entry
            tp = entry - risk * float(settings.pending_tp_r_multiple)
        expiry = int(ob["break_open_time"]) + 8 * 900
        bars = storage.query_all(
            """
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = 'M1' AND is_closed = 1
              AND open_time >= ? AND open_time <= ?
            ORDER BY open_time ASC
            """,
            (symbol, int(ob["break_open_time"]), expiry),
        )
        filled = False
        fill_time = None
        for bar in bars:
            bar_low = float(bar["low"])
            bar_high = float(bar["high"])
            if not filled:
                if bar_low <= entry <= bar_high:
                    filled = True
                    fill_time = int(bar["open_time"])
                else:
                    continue
            # Conservative ordering: if SL and TP are both hit in same M1 bar, count SL first.
            if side == "buy":
                if bar_low <= sl:
                    return self._row(ob, side, entry, sl, tp, fill_time, int(bar["open_time"]), "sl", -1.0)
                if bar_high >= tp:
                    return self._row(ob, side, entry, sl, tp, fill_time, int(bar["open_time"]), "tp", settings.pending_tp_r_multiple)
            else:
                if bar_high >= sl:
                    return self._row(ob, side, entry, sl, tp, fill_time, int(bar["open_time"]), "sl", -1.0)
                if bar_low <= tp:
                    return self._row(ob, side, entry, sl, tp, fill_time, int(bar["open_time"]), "tp", settings.pending_tp_r_multiple)
        return self._row(ob, side, entry, sl, tp, fill_time, expiry, "open" if filled else "expired", 0.0)

    @staticmethod
    def _row(ob: dict[str, Any], side: str, entry: float, sl: float, tp: float, fill_time: int | None,
             exit_time: int, result: str, r_multiple: float) -> dict[str, Any]:
        return {
            "ob_id": int(ob["id"]), "side": side, "break_open_time": int(ob["break_open_time"]),
            "entry": entry, "stop_loss": sl, "take_profit": tp, "fill_time": fill_time,
            "exit_time": exit_time, "result": result, "r_multiple": float(r_multiple),
        }
