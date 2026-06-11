from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse

from app.multibot import db, service
from app.multibot.dashboard import HTML
from app.multibot.models import BotCreate, BotParameterUpdate, CloneBotRequest, ProfileCreate, WalletResetRequest
from app.multibot.runtime import hub

router = APIRouter(tags=["multi-bot"])
db.migrate()


@router.get("/api/multibot/migration/status")
def migration_status():
    return db.status()


@router.get("/api/multibot/runtime/status")
def runtime_status():
    return hub.status()


@router.get("/api/profiles")
def profiles():
    return service.list_profiles()


@router.post("/api/profiles")
def create_profile(payload: ProfileCreate):
    try:
        return service.create_profile(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/profiles/{profile_id}/enable")
def enable_profile(profile_id: int):
    result = service.set_profile_enabled(profile_id, True)
    if result is None:
        raise HTTPException(404, "profile not found")
    return result


@router.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int):
    if not service.delete_profile(profile_id):
        raise HTTPException(404, "profile not found")
    return {"ok": True}


@router.post("/api/profiles/{profile_id}/disable")
def disable_profile(profile_id: int):
    result = service.set_profile_enabled(profile_id, False)
    if result is None:
        raise HTTPException(404, "profile not found")
    return result


@router.get("/api/bots")
def bots(profile_id: int | None = None):
    return service.list_bots(profile_id)


@router.post("/api/bots")
def create_bot(payload: BotCreate):
    try:
        return service.create_bot(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/bots/{bot_id}")
def get_bot(bot_id: int):
    result = service.get_bot(bot_id)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.get("/api/bots/{bot_id}/state")
def get_bot_state(bot_id: int):
    result = service.bot_state(bot_id)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.get("/api/bots/{bot_id}/trades")
def get_bot_trades(bot_id: int, limit: int = 100):
    return service.trades(bot_id, max(1, min(limit, 1000)))


@router.get("/api/bots/{bot_id}/signals")
def get_bot_signals(bot_id: int, limit: int = 100):
    return service.signal_logs(bot_id, max(1, min(limit, 1000)))


@router.post("/api/bots/{bot_id}/clone")
def clone_bot(bot_id: int, payload: CloneBotRequest):
    try:
        return service.clone_bot(bot_id, payload.name)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.delete("/api/bots/{bot_id}")
def delete_bot(bot_id: int):
    if not service.delete_bot(bot_id):
        raise HTTPException(404, "bot not found")
    return {"ok": True}


@router.post("/api/bots/{bot_id}/enable")
def enable_bot(bot_id: int):
    result = service.set_bot_enabled(bot_id, True)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.post("/api/bots/{bot_id}/disable")
def disable_bot(bot_id: int):
    result = service.set_bot_enabled(bot_id, False)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.put("/api/bots/{bot_id}/parameters")
def update_parameters(bot_id: int, payload: BotParameterUpdate):
    result = service.update_bot_parameters(bot_id, payload.parameters)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.get("/api/bots/{bot_id}/wallet")
def wallet(bot_id: int):
    result = service.get_wallet(bot_id)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.post("/api/bots/{bot_id}/wallet/reset")
def reset_wallet(bot_id: int, payload: WalletResetRequest):
    result = service.reset_wallet(bot_id, payload.balance)
    if result is None:
        raise HTTPException(404, "bot not found")
    return result


@router.get("/api/compare")
def compare(bot_ids: str = ""):
    parsed = [int(item) for item in bot_ids.split(",") if item.strip()]
    return service.compare(parsed or None)


@router.websocket("/ws/multibot")
async def ws_multibot(ws: WebSocket):
    await ws.accept()
    hub.clients.add(ws)
    try:
        await ws.send_json({"event": "connected", "runtime": hub.status()})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.clients.discard(ws)
    except Exception:
        hub.clients.discard(ws)


@router.get("/dashboard", response_class=HTMLResponse)
def unified_dashboard():
    return HTML


@router.get("/multi-bot-dashboard")
def dashboard_redirect():
    return RedirectResponse(url="/dashboard", status_code=307)
