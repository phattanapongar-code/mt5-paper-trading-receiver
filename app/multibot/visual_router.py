from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import storage
from app.multibot.visual_engine import execute_graph, get_node_types

router = APIRouter(prefix="/api/visual-strategies", tags=["visual-strategies"])

# ── Models ──


class VisualStrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    graph: dict[str, Any] = Field(..., description="Graph definition with 'nodes' and 'edges'")


class VisualStrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: dict[str, Any] | None = None


class VisualStrategyOut(BaseModel):
    id: int
    name: str
    description: str
    graph: dict[str, Any]
    created_at: int
    updated_at: int


# ── Init table + seed presets ──

def ensure_table() -> None:
    storage.execute(
        """
        CREATE TABLE IF NOT EXISTS visual_strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            graph_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )


_GRAPH_DIR = Path(__file__).parent / "visual_strategies"


def seed_presets() -> None:
    """Seed preset graph JSON files into the visual_strategies table if not already present."""
    ensure_table()
    if not _GRAPH_DIR.is_dir():
        return
    now = int(time.time())
    for fpath in sorted(_GRAPH_DIR.glob("*_graph.json")):
        name = fpath.stem.replace("_graph", "").replace("_", " ").title()
        try:
            graph = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        existing = storage.query_one("SELECT id FROM visual_strategies WHERE name=?", (name,))
        if existing:
            continue
        storage.execute(
            "INSERT OR IGNORE INTO visual_strategies(name, description, graph_json, created_at, updated_at) VALUES (?,?,?,?,?)",
            (name, f"Preset: {name}", json.dumps(graph), now, now),
        )


# ── CRUD ──


@router.get("")
def list_strategies() -> list[dict[str, Any]]:
    ensure_table()
    rows = storage.query_all(
        "SELECT id, name, description, created_at, updated_at FROM visual_strategies ORDER BY updated_at DESC"
    )
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_strategy(body: VisualStrategyCreate) -> dict[str, Any]:
    ensure_table()
    _validate_graph(body.graph)
    now = int(time.time())
    try:
        cur = storage.execute(
            "INSERT INTO visual_strategies(name, description, graph_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.description, json.dumps(body.graph), now, now),
        )
    except Exception as exc:
        raise HTTPException(400, f"Strategy name may already exist: {exc}")
    return {"id": cur.lastrowid, "name": body.name, "description": body.description, "created_at": now, "updated_at": now}


@router.get("/{strategy_id}")
def get_strategy(strategy_id: int) -> VisualStrategyOut:
    ensure_table()
    row = storage.query_one("SELECT * FROM visual_strategies WHERE id=?", (strategy_id,))
    if not row:
        raise HTTPException(404, "Visual strategy not found")
    d = dict(row)
    d["graph"] = json.loads(d.pop("graph_json"))
    return VisualStrategyOut(**d)


@router.put("/{strategy_id}")
def update_strategy(strategy_id: int, body: VisualStrategyUpdate) -> dict[str, Any]:
    ensure_table()
    existing = storage.query_one("SELECT * FROM visual_strategies WHERE id=?", (strategy_id,))
    if not existing:
        raise HTTPException(404, "Visual strategy not found")
    now = int(time.time())
    name = body.name if body.name is not None else existing["name"]
    desc = body.description if body.description is not None else existing["description"]
    graph_json = existing["graph_json"]
    if body.graph is not None:
        _validate_graph(body.graph)
        graph_json = json.dumps(body.graph)
    storage.execute(
        "UPDATE visual_strategies SET name=?, description=?, graph_json=?, updated_at=? WHERE id=?",
        (name, desc, graph_json, now, strategy_id),
    )
    return {"ok": True}


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int) -> dict[str, Any]:
    ensure_table()
    storage.execute("DELETE FROM visual_strategies WHERE id=?", (strategy_id,))
    return {"ok": True}


# ── Test / preview ──


class TestRequest(BaseModel):
    graph: dict[str, Any]
    bid: float
    ask: float
    symbol: str = "XAUUSD"
    timeframe: str = "M15"


@router.post("/test")
def test_strategy(body: TestRequest) -> dict[str, Any]:
    """Execute a visual strategy against provided tick data (no DB persistence)."""
    _validate_graph(body.graph)
    result = execute_graph(
        body.graph,
        bid=body.bid,
        ask=body.ask,
        symbol=body.symbol,
        timeframe=body.timeframe,
    )
    return {"decision": result}


@router.get("/node-types")
def node_types() -> dict[str, str]:
    return get_node_types()


# ── Validation ──


def _validate_graph(graph: dict[str, Any]) -> None:
    nodes = graph.get("nodes", [])
    if not nodes:
        raise HTTPException(400, "Graph must have at least one node")
    # Each node must have id, type
    for n in nodes:
        if not n.get("id"):
            raise HTTPException(400, "Each node must have an 'id'")
        if not n.get("type"):
            raise HTTPException(400, f"Node {n.get('id')} must have a 'type'")
    edges = graph.get("edges", [])
    node_ids = {n["id"] for n in nodes}
    for edge in edges:
        src = edge.get("source", edge.get("from"))
        tgt = edge.get("target", edge.get("to"))
        if src not in node_ids:
            raise HTTPException(400, f"Edge source '{src}' not found in nodes")
        if tgt not in node_ids:
            raise HTTPException(400, f"Edge target '{tgt}' not found in nodes")


# ── Ensure table on import ──

ensure_table()
