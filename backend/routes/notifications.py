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

