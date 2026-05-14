from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import RegisterReq, LoginReq, UserPublic, AuthResp, ForgotPasswordReq, ResetPasswordReq
from core import hash_password, verify_password, create_token
from email_service import send_reset_code_email
import hashlib, secrets

@router.post("/auth/register", response_model=AuthResp)
async def register(req: RegisterReq):
    existing = await db.users.find_one({"email": req.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": req.email.lower(),
        "name": req.name,
        "password": hash_password(req.password),
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(user_doc)
    token = create_token(user_id)
    return AuthResp(
        token=token,
        user=UserPublic(id=user_id, email=req.email.lower(), name=req.name, created_at=user_doc["created_at"]),
    )


@router.post("/auth/login", response_model=AuthResp)
async def login(req: LoginReq):
    user = await db.users.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    token = create_token(user["id"])
    return AuthResp(
        token=token,
        user=UserPublic(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"]),
    )


@router.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(**user)


@router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordReq):
    """Generate a 6-digit reset code, store hashed (30min TTL), send by email via Resend.
    Always returns the same response to avoid leaking which emails exist.
    Rate-limited: max 1 request per 60s per email (prevents email spam/abuse).
    """
    user = await db.users.find_one({"email": req.email.lower()})
    if not user:
        return {"sent": True, "email_sent": False}
    # Rate-limit: refuse if a code was generated less than 60s ago
    recent = await db.password_resets.find_one(
        {"user_id": user["id"], "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(seconds=60)}},
        sort=[("created_at", -1)],
    )
    if recent:
        rcreated = recent["created_at"]
        # Normalise naive datetime → UTC-aware (Mongo strips tzinfo)
        if rcreated.tzinfo is None:
            rcreated = rcreated.replace(tzinfo=timezone.utc)
        secs_ago = int((datetime.now(timezone.utc) - rcreated).total_seconds())
        remaining = max(1, 60 - secs_ago)
        raise HTTPException(
            status_code=429,
            detail=f"Patiente {remaining} secondes avant de redemander un nouveau code.",
        )
    import random, string
    code = "".join(random.choices(string.digits, k=6))
    code_hash = hash_password(code)
    await db.password_resets.delete_many({"user_id": user["id"]})
    await db.password_resets.insert_one({
        "user_id": user["id"],
        "email": user["email"],
        "code_hash": code_hash,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
        "used": False,
    })
    logger.info(f"[PASSWORD-RESET] code generated for user={user['email']}")
    from email_service import send_reset_code_email, is_configured as email_configured
    email_sent = False
    if email_configured():
        try:
            email_sent = await send_reset_code_email(user["email"], code, user.get("name"))
        except Exception as e:
            logger.exception(f"[PASSWORD-RESET] email send error: {e}")
    if not email_sent:
        logger.warning(f"[PASSWORD-RESET] FALLBACK code={code} for {user['email']} (email not sent)")
    return {"sent": True, "email_sent": email_sent}


@router.post("/auth/reset-password", response_model=AuthResp)
async def reset_password(req: ResetPasswordReq):
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (min 6 caractères)")
    user = await db.users.find_one({"email": req.email.lower()})
    if not user:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")
    pr = await db.password_resets.find_one({
        "user_id": user["id"],
        "used": False,
        "expires_at": {"$gte": datetime.now(timezone.utc)},
    }, sort=[("created_at", -1)])
    if not pr:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")
    if not verify_password(req.code, pr["code_hash"]):
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")
    # All good — change password and mark code used
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password": hash_password(req.new_password)}},
    )
    await db.password_resets.update_one(
        {"_id": pr["_id"]},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}},
    )
    token = create_token(user["id"])
    return AuthResp(
        token=token,
        user=UserPublic(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"]),
    )


# ============ MARKET ROUTES (Binance public) ============
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "LTCUSDT", "TRXUSDT", "SHIBUSDT", "ATOMUSDT",
    "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
]

