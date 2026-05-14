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
async def binance_connect(req: BinanceConnectReq, force: bool = False, user=Depends(get_current_user)):
    if not req.api_key or not req.api_secret or len(req.api_key) < 20 or len(req.api_secret) < 20:
        raise HTTPException(status_code=400, detail="Clés invalides")

    # If force=true, skip pre-validation and just store. Used when the cloud
    # server can't reach Binance (geo-block) but the user wants to save anyway.
    if force:
        await db.users.update_one(
            {"id": user["id"]},
            {
                "$set": {
                    "binance_api_key_enc": encrypt_str(req.api_key),
                    "binance_api_secret_enc": encrypt_str(req.api_secret),
                    "binance_connected_at": datetime.now(timezone.utc),
                    "binance_can_trade": True,  # optimistic; bot will verify on first order
                    "binance_unverified": True,
                }
            },
        )
        logger.warning("Binance connected user=%s WITHOUT validation (force=true)", user.get("id"))
        return {
            "ok": True,
            "unverified": True,
            "can_trade": True,
            "account_type": "UNVERIFIED",
            "balances": [],
        }

    # Normal path: validate against Binance (with automatic mirror fallback)
    try:
        cli = BinanceClient(req.api_key, req.api_secret)
        info = await cli.test_connection()
    except Exception as e:
        msg = str(e)[:300]
        logger.error("Binance connect validation failed user=%s err=%s", user.get("id"), msg)
        # Distinguish geo-block vs bad credentials for clearer UX
        if "All Binance endpoints unreachable" in msg or "451" in msg or "403" in msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    "GEO_BLOCKED|Le serveur ne peut pas joindre Binance depuis sa localisation (restriction géographique). "
                    "Tu peux quand même sauvegarder tes clés en mode avancé — le bot tentera de les valider plus tard."
                ),
            )
        if "-2014" in msg or "-2015" in msg or "Signature" in msg or "Invalid API" in msg or "401" in msg:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Clés API invalides ou mal copiées. Vérifie que tu as bien copié les 64 caractères "
                    "de l'API Key ET du Secret, sans espaces."
                ),
            )
        if "IP" in msg and ("restrict" in msg or "white" in msg or "-2015" in msg):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tu as activé la restriction par IP sur ta clé Binance, mais notre serveur n'est pas "
                    "dans la liste. Désactive la restriction IP ou crée une nouvelle clé sans restriction."
                ),
            )
        raise HTTPException(status_code=400, detail=f"Échec de connexion à Binance : {msg}")
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
                "binance_unverified": False,
            }
        },
    )
    logger.info("Binance connected user=%s account_type=%s", user.get("id"), info.get("account_type"))
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

