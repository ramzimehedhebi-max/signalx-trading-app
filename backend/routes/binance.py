from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import BinanceConnectReq
from binance_live import BinanceClient, encrypt_str, decrypt_str
from services.binance_helpers import _get_user_binance

@router.post("/binance/connect")
async def binance_connect(req: BinanceConnectReq, user=Depends(get_current_user)):
    if not req.api_key or not req.api_secret or len(req.api_key) < 20 or len(req.api_secret) < 20:
        raise HTTPException(status_code=400, detail="Clés invalides")
    # First, validate the keys against Binance
    try:
        cli = BinanceClient(req.api_key, req.api_secret)
        info = await cli.test_connection()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Échec de connexion à Binance : {str(e)[:200]}")
    if not info.get("can_trade"):
        raise HTTPException(
            status_code=400,
            detail="La clé n'a pas la permission Spot Trading activée sur Binance.",
        )
    if info.get("can_withdraw"):
        # SECURITY: refuse keys that allow withdrawals
        raise HTTPException(
            status_code=400,
            detail="⚠️ Cette clé autorise les RETRAITS. Pour ta sécurité, désactive 'Enable Withdrawals' sur Binance et recrée la clé.",
        )
    # Encrypt and store
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "binance_api_key_enc": encrypt_str(req.api_key),
                "binance_api_secret_enc": encrypt_str(req.api_secret),
                "binance_connected_at": datetime.now(timezone.utc),
                "binance_can_trade": True,
            }
        },
    )
    return {
        "ok": True,
        "can_trade": info["can_trade"],
        "account_type": info.get("account_type"),
        "balances": info.get("balances", []),
    }


@router.delete("/binance/disconnect")
async def binance_disconnect(user=Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$unset": {
                "binance_api_key_enc": "",
                "binance_api_secret_enc": "",
                "binance_connected_at": "",
                "binance_can_trade": "",
            }
        },
    )
    # Also turn off live mode automatically
    await db.bot_configs.update_one(
        {"user_id": user["id"]},
        {"$set": {"live_mode": False}},
    )
    return {"ok": True}


@router.get("/binance/status")
async def binance_status(user=Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not u or not u.get("binance_api_key_enc"):
        return {"connected": False}
    return {
        "connected": True,
        "connected_at": u.get("binance_connected_at"),
        "can_trade": u.get("binance_can_trade", False),
    }


@router.get("/binance/account")
async def binance_account(user=Depends(get_current_user)):
    cli = await _get_user_binance(user["id"])
    if not cli:
        raise HTTPException(status_code=400, detail="Binance non connecté")
    try:
        balances = await cli.get_balances()
        return {"balances": balances}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur Binance: {str(e)[:200]}")


# ============ STRIPE PREMIUM SUBSCRIPTIONS ============
PRICE_EUR = 9.99
FREE_MAX_PAIRS = 3
FREE_MAX_PREDICTIONS_PER_DAY = 1

