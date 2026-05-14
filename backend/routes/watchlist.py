from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import WatchlistItem, AddWatchReq, AlertCreateReq, Alert

@router.get("/watchlist")
async def list_watchlist(user=Depends(get_current_user)):
    cur = db.watchlist.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    items = await cur.to_list(200)
    return items


@router.post("/watchlist")
async def add_watchlist(req: AddWatchReq, user=Depends(get_current_user)):
    sym = req.symbol.upper()
    existing = await db.watchlist.find_one({"user_id": user["id"], "symbol": sym})
    if existing:
        raise HTTPException(status_code=400, detail="Déjà dans la watchlist")
    item = WatchlistItem(user_id=user["id"], symbol=sym)
    await db.watchlist.insert_one(item.dict())
    return item


@router.delete("/watchlist/{symbol}")
async def remove_watchlist(symbol: str, user=Depends(get_current_user)):
    res = await db.watchlist.delete_one({"user_id": user["id"], "symbol": symbol.upper()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Symbole non trouvé")
    return {"ok": True}


# ============ ALERTS ============
@router.get("/alerts")
async def list_alerts(user=Depends(get_current_user)):
    cur = db.alerts.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    return await cur.to_list(200)


@router.post("/alerts")
async def create_alert(req: AlertCreateReq, user=Depends(get_current_user)):
    if req.direction not in ("above", "below"):
        raise HTTPException(status_code=400, detail="Direction invalide")
    a = Alert(user_id=user["id"], symbol=req.symbol.upper(), target_price=req.target_price, direction=req.direction)
    await db.alerts.insert_one(a.dict())
    return a


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, user=Depends(get_current_user)):
    res = await db.alerts.delete_one({"user_id": user["id"], "id": alert_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return {"ok": True}


