from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from app import storage
from app.backtest.models import BacktestRequest
from app.backtest.engine import BacktestEngine
from app.multibot.db import default_parameters, json_text

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(req: BacktestRequest) -> dict[str, Any]:
    if req.start_time >= req.end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")
    engine = BacktestEngine(req)
    report = engine.run()
    if not report.get("ok", True):
        raise HTTPException(status_code=400, detail=report.get("error", "Backtest failed"))
    now = int(time.time())
    storage.execute(
        """
        INSERT INTO backtest_runs(
            strategy_type,symbol,timeframe,parameters_json,start_time,end_time,config_json,
            total_trades,wins,losses,win_rate,net_pnl,gross_profit,gross_loss,
            profit_factor,sharpe_ratio,max_drawdown_pct,avg_r,total_r,final_balance,return_pct,
            equity_curve_json,trades_json,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "visual", req.symbol, req.timeframe, json_text(req.parameters),
            req.start_time, req.end_time, json_text(req.model_dump()),
            report["total_trades"], report["wins"], report["losses"], report["win_rate"],
            report["net_pnl"], report["gross_profit"], report["gross_loss"],
            report["profit_factor"], report["sharpe_ratio"], report["max_drawdown_pct"],
            report["avg_r"], report["total_r"], report["final_balance"], report["return_pct"],
            json_text(report["equity_curve"]), json_text(report["trades"]), now,
        ),
    )
    report["run_id"] = storage.query_one("SELECT last_insert_rowid() AS id")["id"]
    return report


@router.get("/history")
def backtest_history(limit: int = 20) -> list[dict[str, Any]]:
    return storage.query_all(
        """
        SELECT id,strategy_type,symbol,timeframe,start_time,end_time,
               total_trades,net_pnl,win_rate,profit_factor,sharpe_ratio,
               max_drawdown_pct,return_pct,created_at
        FROM backtest_runs ORDER BY id DESC LIMIT ?
        """,
        (max(1, min(limit, 100)),),
    )


@router.get("/runs/{run_id}")
def backtest_run(run_id: int) -> dict[str, Any]:
    report = storage.query_one("SELECT * FROM backtest_runs WHERE id=?", (run_id,))
    if report is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    report["equity_curve"] = json.loads(report.get("equity_curve_json", "[]"))
    report["trades"] = json.loads(report.get("trades_json", "[]"))
    return report


@router.get("/optimize/history")
def optimize_history(limit: int = 20) -> list[dict[str, Any]]:
    return storage.query_all(
        """
        SELECT id,strategy_type,symbol,timeframe,start_time,end_time,
               optimization_metric,total_combinations,created_at
        FROM backtest_optimize_runs ORDER BY id DESC LIMIT ?
        """,
        (max(1, min(limit, 100)),),
    )


@router.get("/optimize/runs/{run_id}")
def optimize_run(run_id: int) -> dict[str, Any]:
    run = storage.query_one("SELECT * FROM backtest_optimize_runs WHERE id=?", (run_id,))
    if run is None:
        raise HTTPException(status_code=404, detail="Optimize run not found")
    run["param_ranges"] = json.loads(run.get("param_ranges_json", "{}"))
    run["results"] = json.loads(run.get("results_json", "[]"))
    return run


@router.post("/clone-bot/{run_id}")
def clone_best_params(run_id: int) -> dict[str, Any]:
    report = storage.query_one("SELECT * FROM backtest_runs WHERE id=?", (run_id,))
    if report is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    params = json.loads(report.get("parameters_json", "{}"))
    default_params = default_parameters()
    default_params.update(params)

    now = int(time.time())
    profile = storage.query_one("SELECT id FROM profiles ORDER BY id LIMIT 1")
    profile_id = profile["id"] if profile else 1

    # Extract visual_strategy_id from config_json if available
    visual_strategy_id = None
    try:
        config = json.loads(report.get("config_json", "{}"))
        visual_strategy_id = config.get("visual_strategy_id")
    except Exception:
        pass

    name = f"Backtest #{run_id}"
    cur = storage.execute(
        "INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,visual_strategy_id,created_at,updated_at) VALUES(?,?,?,?,?,?,0,?,?,?,?)",
        (profile_id, name, "visual", "v1", report["symbol"], report["timeframe"], json_text(params), visual_strategy_id, now, now),
    )
    bot_id = cur.lastrowid
    storage.execute(
        "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,?,?,0,?,?,?)",
        (bot_id, report["final_balance"], report["final_balance"], report["final_balance"], now, now),
    )
    storage.execute("INSERT OR IGNORE INTO bot_runtime_state(bot_id,updated_at) VALUES(?,?)", (bot_id, now))
    return {"ok": True, "bot_id": bot_id, "name": name}
