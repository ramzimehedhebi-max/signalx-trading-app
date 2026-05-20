from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import PushTokenReq


@router.post("/user/push-token")
async def save_push_token(req: PushTokenReq, user=Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"push_token": req.token}}
    )
    return {"ok": True}


@router.get("/notifications")
async def list_notifications(user=Depends(get_current_user), limit: int = 50):
    cur = db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cur.to_list(limit)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"items": items, "unread": unread}


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, user=Depends(get_current_user)):
    await db.notifications.update_one(
        {"id": notif_id, "user_id": user["id"]}, {"$set": {"read": True}}
    )
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(user=Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True}


@router.get("/notifications/unread-count")
async def unread_count(user=Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"unread": n}


# ---------------- TELEGRAM ----------------

@router.get("/notifications/telegram/status")
async def telegram_status(user=Depends(get_current_user)):
    """Check whether Telegram bot is configured server-side."""
    from services.notifications import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    return {
        "configured": bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID),
        "token_set": bool(TELEGRAM_BOT_TOKEN),
        "chat_id_set": bool(TELEGRAM_CHAT_ID),
    }


@router.post("/notifications/telegram/test")
async def telegram_test(user=Depends(get_current_user)):
    """Send a test Telegram message to verify the setup."""
    from services.notifications import _send_telegram, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(
            status_code=400,
            detail="Telegram non configuré : ajoute TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans le .env du serveur.",
        )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = (
        "<b>✅ Test SignalX → Telegram</b>\n\n"
        f"👤 Utilisateur : <code>{user.get('email', '?')}</code>\n"
        f"🕐 Heure : {now}\n\n"
        "<i>Si tu lis ce message, les notifications Telegram sont actives. "
        "Tu recevras désormais une alerte à chaque trade LIVE (achat / clôture / erreur).</i>"
    )
    ok = await _send_telegram(msg)
    if not ok:
        raise HTTPException(status_code=502, detail="Échec d'envoi Telegram. Vérifie le token et le chat_id.")
    return {"ok": True, "message": "Message Telegram envoyé"}

