from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.multibot import db, service
from app.multibot.models import BotCreate, CloneBotRequest, ProfileCreate, WalletResetRequest
from app.multibot.dashboard import HTML

router = APIRouter(tags=["multi-bot"])

# Safe to call repeatedly; ensures schema exists after every restart.
db.migrate()

@router.get("/api/multibot/migration/status")
def migration_status():
    return db.status()

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

@router.post("/api/bots/{bot_id}/clone")
def clone_bot(bot_id: int, payload: CloneBotRequest):
    try:
        return service.clone_bot(bot_id, payload.name)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))

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

@router.get("/api/bots/{bot_id}/wallet")
def wallet(bot_id: int):
    result = service.get_bot(bot_id)
    if result is None:
        raise HTTPException(404, "bot not found")
    return {k: result[k] for k in ("wallet_id", "initial_balance", "balance", "realized_pnl", "currency", "max_drawdown", "peak_equity")}

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

@router.get("/multi-bot-dashboard", response_class=HTMLResponse)
def dashboard():
    return HTML
