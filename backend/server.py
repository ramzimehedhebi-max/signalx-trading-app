from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt as pyjwt
import httpx
import asyncio
import json

from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Binance Live trading helpers (signed REST + Fernet encryption)
from binance_live import (
    BinanceClient,
    encrypt_str,
    decrypt_str,
    round_step,
    extract_executed,
)

# Stripe subscriptions
import stripe_subs

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = os.environ.get('JWT_ALG', 'HS256')
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '43200'))
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

BINANCE_BASE = "https://data-api.binance.vision"

app = FastAPI(title="Crypto Signals API")
api_router = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)


# ============ MODELS ============
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime


class AuthResp(BaseModel):
    token: str
    user: UserPublic


class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AddWatchReq(BaseModel):
    symbol: str


class AlertCreateReq(BaseModel):
    symbol: str
    target_price: float
    direction: str  # "above" or "below"


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    target_price: float
    direction: str
    triggered: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PositionCreateReq(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    side: str = "long"  # long/short


class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    quantity: float
    entry_price: float
    side: str = "long"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalReq(BaseModel):
    symbol: str
    interval: str = "1h"


class SignalResp(BaseModel):
    symbol: str
    interval: str
    action: str  # BUY / SELL / HOLD
    confidence: int  # 0-100
    entry: Optional[float] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None
    timeframe: str
    reasoning: str
    indicators: dict
    generated_at: datetime


# ============ AUTH HELPERS ============
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=401, detail="Authentification requise")
    try:
        payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


# ============ AUTH ROUTES ============
@api_router.post("/auth/register", response_model=AuthResp)
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


@api_router.post("/auth/login", response_model=AuthResp)
async def login(req: LoginReq):
    user = await db.users.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    token = create_token(user["id"])
    return AuthResp(
        token=token,
        user=UserPublic(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"]),
    )


@api_router.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(**user)


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class ResetPasswordReq(BaseModel):
    email: EmailStr
    code: str
    new_password: str


@api_router.post("/auth/forgot-password")
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


@api_router.post("/auth/reset-password", response_model=AuthResp)
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


@api_router.get("/market/tickers")
async def get_tickers(symbols: Optional[str] = None):
    """Get 24h ticker stats. symbols param is comma-separated, optional."""
    syms = symbols.split(",") if symbols else DEFAULT_SYMBOLS
    syms = [s.upper() for s in syms]
    async with httpx.AsyncClient(timeout=10.0) as cli:
        # Use /api/v3/ticker/24hr with symbols array
        params = {"symbols": json.dumps(syms, separators=(",", ":"))}
        try:
            r = await cli.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Binance tickers error: {e}")
            raise HTTPException(status_code=502, detail="Erreur de chargement des données Binance")

    result = []
    for d in data:
        result.append({
            "symbol": d["symbol"],
            "lastPrice": float(d["lastPrice"]),
            "priceChange": float(d["priceChange"]),
            "priceChangePercent": float(d["priceChangePercent"]),
            "highPrice": float(d["highPrice"]),
            "lowPrice": float(d["lowPrice"]),
            "volume": float(d["volume"]),
            "quoteVolume": float(d["quoteVolume"]),
        })
    # sort by volume desc
    result.sort(key=lambda x: x["quoteVolume"], reverse=True)
    return result


@api_router.get("/market/ticker/{symbol}")
async def get_ticker(symbol: str):
    symbol = symbol.upper()
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params={"symbol": symbol})
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            logger.error(f"Binance ticker error: {e}")
            raise HTTPException(status_code=502, detail="Symbole introuvable")
    return {
        "symbol": d["symbol"],
        "lastPrice": float(d["lastPrice"]),
        "priceChange": float(d["priceChange"]),
        "priceChangePercent": float(d["priceChangePercent"]),
        "highPrice": float(d["highPrice"]),
        "lowPrice": float(d["lowPrice"]),
        "volume": float(d["volume"]),
        "quoteVolume": float(d["quoteVolume"]),
        "openPrice": float(d["openPrice"]),
    }


@api_router.get("/market/klines/{symbol}")
async def get_klines(symbol: str, interval: str = "1h", limit: int = 100):
    symbol = symbol.upper()
    if interval not in ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]:
        raise HTTPException(status_code=400, detail="Intervalle invalide")
    limit = min(max(limit, 10), 500)
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Binance klines error: {e}")
            raise HTTPException(status_code=502, detail="Erreur de chargement des bougies")

    klines = []
    for k in data:
        klines.append({
            "openTime": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "closeTime": k[6],
        })
    return klines


# ============ INDICATORS HELPERS ============
def compute_sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def compute_ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def compute_rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        ch = values[i] - values[i - 1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ============ AI SIGNAL ============
@api_router.post("/ai/signal", response_model=SignalResp)
async def generate_signal(req: SignalReq, user=Depends(get_current_user)):
    symbol = req.symbol.upper()
    interval = req.interval

    # Fetch klines
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": 100},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Binance klines error: {e}")
            raise HTTPException(status_code=502, detail="Données indisponibles")

    closes = [float(k[4]) for k in data]
    highs = [float(k[2]) for k in data]
    lows = [float(k[3]) for k in data]
    last_close = closes[-1]

    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    ema12 = compute_ema(closes, 12)
    ema26 = compute_ema(closes, 26)
    rsi14 = compute_rsi(closes, 14)
    high_50 = max(closes[-50:]) if len(closes) >= 50 else max(closes)
    low_50 = min(closes[-50:]) if len(closes) >= 50 else min(closes)
    change_pct = ((last_close - closes[0]) / closes[0]) * 100 if closes[0] else 0

    indicators = {
        "lastPrice": round(last_close, 6),
        "sma20": round(sma20, 6) if sma20 else None,
        "sma50": round(sma50, 6) if sma50 else None,
        "ema12": round(ema12, 6) if ema12 else None,
        "ema26": round(ema26, 6) if ema26 else None,
        "rsi14": round(rsi14, 2) if rsi14 else None,
        "high50": round(high_50, 6),
        "low50": round(low_50, 6),
        "change_pct_period": round(change_pct, 2),
    }

    # Build prompt for Claude
    system_msg = (
        "Tu es un analyste technique crypto expert. Tu analyses des données de marché Binance et "
        "renvoies STRICTEMENT un JSON valide (aucun texte avant ou après) avec les champs suivants:\n"
        "{\n"
        '  "action": "BUY" | "SELL" | "HOLD",\n'
        '  "confidence": int (0-100),\n'
        '  "entry": float | null,\n'
        '  "target": float | null,\n'
        '  "stop_loss": float | null,\n'
        '  "timeframe": "court terme" | "moyen terme" | "long terme",\n'
        '  "reasoning": "Explication concise en français (3-4 phrases) basée sur les indicateurs."\n'
        "}\n"
        "Sois rigoureux, prudent, mentionne les risques. Pas d'emoji. Pas de markdown."
    )

    user_text = (
        f"Symbole: {symbol}\nIntervalle: {interval}\n"
        f"Prix actuel: {last_close}\n"
        f"SMA20: {indicators['sma20']}\n"
        f"SMA50: {indicators['sma50']}\n"
        f"EMA12: {indicators['ema12']}\n"
        f"EMA26: {indicators['ema26']}\n"
        f"RSI(14): {indicators['rsi14']}\n"
        f"Plus haut 50 périodes: {indicators['high50']}\n"
        f"Plus bas 50 périodes: {indicators['low50']}\n"
        f"Variation sur la période: {indicators['change_pct_period']}%\n"
        f"\nDonne un signal d'achat/vente avec niveaux d'entrée, cible et stop-loss."
    )

    session_id = f"signal-{symbol}-{interval}-{user['id']}-{int(datetime.now(timezone.utc).timestamp())}"
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_msg,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    try:
        response_text = await chat.send_message(UserMessage(text=user_text))
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=502, detail="Service IA indisponible")

    # Try parse JSON. Sometimes LLM might wrap in code fences.
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to parse LLM response: {response_text}")
        # fallback simple rule
        action = "HOLD"
        if rsi14 and rsi14 < 30:
            action = "BUY"
        elif rsi14 and rsi14 > 70:
            action = "SELL"
        parsed = {
            "action": action,
            "confidence": 55,
            "entry": last_close,
            "target": last_close * 1.05,
            "stop_loss": last_close * 0.97,
            "timeframe": "court terme",
            "reasoning": "Analyse fallback basée sur RSI. La réponse IA n'a pas pu être parsée.",
        }

    signal = SignalResp(
        symbol=symbol,
        interval=interval,
        action=str(parsed.get("action", "HOLD")).upper(),
        confidence=int(parsed.get("confidence", 50)),
        entry=parsed.get("entry"),
        target=parsed.get("target"),
        stop_loss=parsed.get("stop_loss"),
        timeframe=str(parsed.get("timeframe", "court terme")),
        reasoning=str(parsed.get("reasoning", "")),
        indicators=indicators,
        generated_at=datetime.now(timezone.utc),
    )

    # Cache signal in DB
    sig_doc = signal.dict()
    sig_doc["id"] = str(uuid.uuid4())
    sig_doc["user_id"] = user["id"]
    await db.signals.insert_one(sig_doc)

    return signal


@api_router.get("/ai/signals/recent")
async def recent_signals(user=Depends(get_current_user), limit: int = 20):
    cur = db.signals.find({"user_id": user["id"]}, {"_id": 0}).sort("generated_at", -1).limit(limit)
    items = await cur.to_list(limit)
    return items


# ============ WATCHLIST ============
@api_router.get("/watchlist")
async def list_watchlist(user=Depends(get_current_user)):
    cur = db.watchlist.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    items = await cur.to_list(200)
    return items


@api_router.post("/watchlist")
async def add_watchlist(req: AddWatchReq, user=Depends(get_current_user)):
    sym = req.symbol.upper()
    existing = await db.watchlist.find_one({"user_id": user["id"], "symbol": sym})
    if existing:
        raise HTTPException(status_code=400, detail="Déjà dans la watchlist")
    item = WatchlistItem(user_id=user["id"], symbol=sym)
    await db.watchlist.insert_one(item.dict())
    return item


@api_router.delete("/watchlist/{symbol}")
async def remove_watchlist(symbol: str, user=Depends(get_current_user)):
    res = await db.watchlist.delete_one({"user_id": user["id"], "symbol": symbol.upper()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Symbole non trouvé")
    return {"ok": True}


# ============ ALERTS ============
@api_router.get("/alerts")
async def list_alerts(user=Depends(get_current_user)):
    cur = db.alerts.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    return await cur.to_list(200)


@api_router.post("/alerts")
async def create_alert(req: AlertCreateReq, user=Depends(get_current_user)):
    if req.direction not in ("above", "below"):
        raise HTTPException(status_code=400, detail="Direction invalide")
    a = Alert(user_id=user["id"], symbol=req.symbol.upper(), target_price=req.target_price, direction=req.direction)
    await db.alerts.insert_one(a.dict())
    return a


@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, user=Depends(get_current_user)):
    res = await db.alerts.delete_one({"user_id": user["id"], "id": alert_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return {"ok": True}


# ============ PORTFOLIO ============
@api_router.get("/portfolio")
async def get_portfolio(user=Depends(get_current_user)):
    cur = db.positions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    positions = await cur.to_list(200)

    if not positions:
        return {"positions": [], "total_invested": 0, "total_value": 0, "total_pnl": 0, "total_pnl_pct": 0}

    # fetch current prices in one call
    symbols = list({p["symbol"] for p in positions})
    # Also fix portfolio price call
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            )
            r.raise_for_status()
            prices = {item["symbol"]: float(item["price"]) for item in r.json()}
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            prices = {}

    total_invested = 0.0
    total_value = 0.0
    enriched = []
    for p in positions:
        cur_price = prices.get(p["symbol"], p["entry_price"])
        invested = p["entry_price"] * p["quantity"]
        value = cur_price * p["quantity"]
        pnl = (value - invested) if p.get("side", "long") == "long" else (invested - value)
        pnl_pct = (pnl / invested * 100) if invested else 0
        enriched.append({
            **p,
            "current_price": cur_price,
            "invested": invested,
            "current_value": value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
        total_invested += invested
        total_value += value

    total_pnl = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
    return {
        "positions": enriched,
        "total_invested": total_invested,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


@api_router.post("/portfolio")
async def add_position(req: PositionCreateReq, user=Depends(get_current_user)):
    if req.quantity <= 0 or req.entry_price <= 0:
        raise HTTPException(status_code=400, detail="Valeurs invalides")
    pos = Position(
        user_id=user["id"],
        symbol=req.symbol.upper(),
        quantity=req.quantity,
        entry_price=req.entry_price,
        side=req.side,
    )
    await db.positions.insert_one(pos.dict())
    return pos


@api_router.delete("/portfolio/{position_id}")
async def remove_position(position_id: str, user=Depends(get_current_user)):
    res = await db.positions.delete_one({"user_id": user["id"], "id": position_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Position introuvable")
    return {"ok": True}


async def _get_cached_prediction(symbol: str, horizon: str = "24h", max_age_min: int = 60):
    """Fetch a cached prediction (from db.predictions). Returns None if too old/missing."""
    cached = await db.predictions.find_one({"key": f"predict:{symbol}:{horizon}"}, {"_id": 0, "key": 0})
    if not cached:
        return None
    gen = cached.get("generated_at")
    if not gen:
        return None
    if gen.tzinfo is None:
        gen = gen.replace(tzinfo=timezone.utc)
    age_min = (datetime.now(timezone.utc) - gen).total_seconds() / 60
    if age_min > max_age_min:
        return None
    return cached


async def _fetch_or_compute_prediction(symbol: str, horizon: str = "24h"):
    """Get a prediction: from cache if fresh, else compute new one. Returns dict or None on error."""
    cached = await _get_cached_prediction(symbol, horizon, max_age_min=60)
    if cached:
        return cached
    try:
        # Call ai_predict logic directly without auth context (used by bot engine).
        # We need a minimal user dict for the dependency. Bypass by replicating core logic:
        interval_map = {"24h": "1h", "3d": "4h", "7d": "1d"}
        interval = interval_map.get(horizon, "1h")
        async with httpx.AsyncClient(timeout=12.0) as cli:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": 100},
            )
            r.raise_for_status()
            data = r.json()
        closes = [float(k[4]) for k in data]
        highs = [float(k[2]) for k in data]
        lows = [float(k[3]) for k in data]
        vols = [float(k[5]) for k in data]
        last = closes[-1]
        rsi = compute_rsi(closes, 14) or 50
        ema12 = compute_ema(closes, 12)
        ema26 = compute_ema(closes, 26)
        change_24h = (closes[-1] - closes[-24]) / closes[-24] * 100 if len(closes) >= 24 else 0
        rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(max(1, len(closes) - 24), len(closes))]
        avg = sum(rets) / len(rets) if rets else 0
        vol_std = (sum((x - avg) ** 2 for x in rets) / len(rets)) ** 0.5 if rets else 0
        volatility_pct = vol_std * 100

        system_msg = (
            "Tu es un analyste quantitatif crypto. Réponds STRICTEMENT en JSON:\n"
            '{"direction":"HAUSSE|STABLE|BAISSE","confidence":int,"target_low":float,'
            '"target_median":float,"target_high":float,"action":"BUY|WAIT|SELL",'
            '"key_factors":["..."],"reasoning":"..."}'
        )
        user_text = (
            f"{symbol} {horizon}\nPrix:{last:.6f} RSI:{rsi:.1f} EMA12:{ema12:.6f} EMA26:{ema26:.6f}\n"
            f"24h:{change_24h:+.2f}% Vol:{volatility_pct:.2f}%\n"
            f"Prédis le prix dans {horizon}."
        )
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"bot-pred-{symbol}-{int(datetime.now(timezone.utc).timestamp())}",
            system_message=system_msg,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=user_text))
        cleaned = resp.strip().strip("`").lstrip("json").strip()
        parsed = json.loads(cleaned)
        result = {
            "symbol": symbol,
            "horizon": horizon,
            "current_price": last,
            "direction": str(parsed.get("direction", "STABLE")).upper(),
            "confidence": int(parsed.get("confidence", 50)),
            "target_low": float(parsed.get("target_low", last * 0.97)),
            "target_median": float(parsed.get("target_median", last)),
            "target_high": float(parsed.get("target_high", last * 1.03)),
            "action": str(parsed.get("action", "WAIT")).upper(),
            "key_factors": parsed.get("key_factors", []),
            "reasoning": str(parsed.get("reasoning", "")),
            "generated_at": datetime.now(timezone.utc),
        }
        await db.predictions.update_one(
            {"key": f"predict:{symbol}:{horizon}"},
            {"$set": {**result, "key": f"predict:{symbol}:{horizon}"}},
            upsert=True,
        )
        return result
    except Exception as e:
        logger.warning(f"Prediction error {symbol}: {e}")
        return None


class PushTokenReq(BaseModel):
    token: str


@api_router.post("/user/push-token")
async def save_push_token(req: PushTokenReq, user=Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"push_token": req.token}}
    )
    return {"ok": True}


@api_router.get("/notifications")
async def list_notifications(user=Depends(get_current_user), limit: int = 50):
    cur = db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cur.to_list(limit)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"items": items, "unread": unread}


@api_router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, user=Depends(get_current_user)):
    await db.notifications.update_one(
        {"id": notif_id, "user_id": user["id"]}, {"$set": {"read": True}}
    )
    return {"ok": True}


@api_router.post("/notifications/read-all")
async def mark_all_read(user=Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True}


@api_router.get("/notifications/unread-count")
async def unread_count(user=Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"unread": n}


async def _send_push(push_token: str, title: str, body: str, data: dict = None):
    if not push_token or not push_token.startswith("ExponentPushToken"):
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            await cli.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": push_token,
                    "sound": "default",
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "priority": "high",
                },
            )
    except Exception as e:
        logger.warning(f"Push send failed: {e}")


async def _create_notification(user_id: str, ntype: str, title: str, body: str, data: dict = None):
    notif = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": ntype,
        "title": title,
        "body": body,
        "data": data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc),
    }
    await db.notifications.insert_one(notif)
    # Send push if user has token
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "push_token": 1})
    if user and user.get("push_token"):
        await _send_push(user["push_token"], title, body, {"type": ntype, **(data or {})})


# ============ TRADING BOT (PAPER) ============
DEFAULT_BOT_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT",
]


# ============ BINANCE LIVE TRADING ============
class BinanceConnectReq(BaseModel):
    api_key: str
    api_secret: str


async def _get_user_binance(user_id: str) -> Optional[BinanceClient]:
    """Build a BinanceClient from the user's stored encrypted keys. None if not connected."""
    u = await db.users.find_one({"id": user_id})
    if not u or not u.get("binance_api_key_enc") or not u.get("binance_api_secret_enc"):
        return None
    try:
        k = decrypt_str(u["binance_api_key_enc"])
        s = decrypt_str(u["binance_api_secret_enc"])
        return BinanceClient(k, s)
    except Exception as e:
        logger.error(f"Binance decrypt error user={user_id}: {e}")
        return None


@api_router.post("/binance/connect")
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


@api_router.delete("/binance/disconnect")
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


@api_router.get("/binance/status")
async def binance_status(user=Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not u or not u.get("binance_api_key_enc"):
        return {"connected": False}
    return {
        "connected": True,
        "connected_at": u.get("binance_connected_at"),
        "can_trade": u.get("binance_can_trade", False),
    }


@api_router.get("/binance/account")
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


async def _get_premium_status(user_id: str) -> dict:
    u = await db.users.find_one({"id": user_id}) or {}
    # Lifetime premium override (founder / lifetime grant)
    if u.get("lifetime_premium"):
        return {
            "is_premium": True,
            "status": "lifetime",
            "current_period_end": None,
            "cancel_at_period_end": False,
            "stripe_configured": stripe_subs.is_configured(),
            "lifetime": True,
        }
    sub_status = u.get("subscription_status")
    is_premium = stripe_subs.is_premium_status(sub_status or "")
    return {
        "is_premium": is_premium,
        "status": sub_status,
        "current_period_end": u.get("current_period_end"),
        "cancel_at_period_end": u.get("cancel_at_period_end", False),
        "stripe_configured": stripe_subs.is_configured(),
        "lifetime": False,
    }


@api_router.get("/premium/status")
async def premium_status(user=Depends(get_current_user)):
    return await _get_premium_status(user["id"])


class PremiumCheckoutReq(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@api_router.post("/premium/checkout")
async def premium_checkout(req: PremiumCheckoutReq = None, user=Depends(get_current_user)):
    if not stripe_subs.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Paiements indisponibles — Stripe n'est pas encore configuré côté serveur.",
        )
    u = await db.users.find_one({"id": user["id"]})
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    try:
        customer_id = await stripe_subs.get_or_create_customer(db, u)
        sess = stripe_subs.create_checkout_session(
            customer_id,
            user["id"],
            success_url=(req.success_url if req else None),
            cancel_url=(req.cancel_url if req else None),
        )
        return sess
    except Exception as e:
        logger.exception(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)[:200]}")


@api_router.post("/premium/cancel")
async def premium_cancel(user=Depends(get_current_user)):
    """Cancel at period end (user keeps access until end of paid period)."""
    if not stripe_subs.is_configured():
        raise HTTPException(status_code=503, detail="Stripe non configuré")
    u = await db.users.find_one({"id": user["id"]})
    if not u or not u.get("subscription_id"):
        raise HTTPException(status_code=400, detail="Aucun abonnement actif")
    try:
        import stripe
        sub = stripe.Subscription.modify(u["subscription_id"], cancel_at_period_end=True)
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"cancel_at_period_end": True}},
        )
        return {"ok": True, "cancel_at_period_end": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ----- Stripe HTTPS bridge → deep-link back into Expo app -----
# Chrome blocks direct exp:// redirects from HTTPS, so Stripe redirects HERE first,
# this page does a JS deep-link to the app scheme.
from fastapi.responses import HTMLResponse

_BRIDGE_HTML = """<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Retour à SignalX…</title>
<style>
  html,body{margin:0;background:#0B0B10;color:#fff;font-family:-apple-system,Segoe UI,Roboto,sans-serif;height:100%;}
  .wrap{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center;gap:16px;}
  .check{width:84px;height:84px;border-radius:50%;background:rgba(0,227,150,0.15);border:2px solid rgba(0,227,150,0.4);display:flex;align-items:center;justify-content:center;font-size:48px;color:#00E396;}
  .cancel{width:84px;height:84px;border-radius:50%;background:rgba(255,69,96,0.12);border:2px solid rgba(255,69,96,0.35);display:flex;align-items:center;justify-content:center;font-size:48px;color:#FF4560;}
  h1{font-size:24px;margin:0;font-weight:900;}
  p{color:#bbb;margin:0;font-size:15px;max-width:320px;line-height:1.55;}
  .hint{background:rgba(243,186,47,0.12);border:1px solid rgba(243,186,47,0.35);padding:14px 16px;border-radius:14px;font-size:14px;color:#fff;max-width:340px;line-height:1.5;}
  .hint b{color:#F3BA2F;}
  a.btn{display:inline-block;padding:14px 26px;background:#F3BA2F;color:#000;font-weight:800;border-radius:999px;text-decoration:none;font-size:15px;}
  .small{color:#666;font-size:12px;margin-top:8px;line-height:1.5;}
</style>
</head><body>
<div class="wrap">
  <div class="__ICON_CLASS__">__ICON__</div>
  <h1>__TITLE__</h1>
  <p>__MSG__</p>
  <div class="hint">
    👉 <b>Ferme cet onglet</b> et reviens dans l'app SignalX.<br/>
    L'activation est automatique sur ton compte.
  </div>
  <a id="back" class="btn" href="__DEEPLINK__">Retour à SignalX</a>
  <div class="small">Astuce : appuie sur la flèche "retour" de ton téléphone<br/>pour revenir directement dans l'app.</div>
</div>
<script>
  var DEEPLINK = "__DEEPLINK__";
  // Try to deep-link automatically right away
  setTimeout(function(){ try { window.location.href = DEEPLINK; } catch(e){} }, 300);
  document.body.addEventListener('click', function(){ try { window.location.href = DEEPLINK; } catch(e){} });
</script>
</body></html>"""


@app.get("/api/stripe/return")
async def stripe_return(
    paid: str = "1",
    target: str = "",
    session_id: str = "",
):
    """HTTPS bridge: Stripe redirects HERE → this page deep-links to the app via JS.
    `target` is a URL-encoded deep link like exp://...../premium that we relay to.
    """
    import urllib.parse
    deeplink = urllib.parse.unquote(target) if target else "signalx://premium"
    sep = "&" if "?" in deeplink else "?"
    deeplink = f"{deeplink}{sep}paid={paid}"
    if session_id:
        deeplink += f"&session_id={urllib.parse.quote(session_id)}"
    if paid == "1":
        title = "Paiement reçu !"
        msg = "Ton abonnement Premium SignalX est en cours d'activation. Cela prend environ 5 à 15 secondes."
        icon_class = "check"
        icon = "✓"
    else:
        title = "Paiement annulé"
        msg = "Aucun montant n'a été débité. Tu peux réessayer à tout moment depuis l'app."
        icon_class = "cancel"
        icon = "✕"
    html = (
        _BRIDGE_HTML
        .replace("__TITLE__", title)
        .replace("__MSG__", msg)
        .replace("__ICON__", icon)
        .replace("__ICON_CLASS__", icon_class)
        .replace("__DEEPLINK__", deeplink)
    )
    return HTMLResponse(content=html)


# NOTE: webhook is mounted on the main app (not api_router) to keep the raw body
@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_subs.verify_webhook(payload, sig)
    except Exception as e:
        logger.warning(f"Stripe webhook verify failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    etype = event["type"]
    obj = event["data"]["object"]
    customer_id = obj.get("customer")
    user_doc = None
    if customer_id:
        user_doc = await db.users.find_one({"stripe_customer_id": customer_id})

    try:
        if etype in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            sub = obj
            if user_doc:
                upd = {
                    "subscription_id": sub.get("id"),
                    "subscription_status": sub.get("status"),
                    "current_period_end": datetime.fromtimestamp(
                        sub.get("current_period_end"), tz=timezone.utc
                    )
                    if sub.get("current_period_end")
                    else None,
                    "cancel_at_period_end": sub.get("cancel_at_period_end", False),
                    "premium_updated_at": datetime.now(timezone.utc),
                }
                await db.users.update_one({"id": user_doc["id"]}, {"$set": upd})
                # Notify
                if etype == "customer.subscription.created":
                    await _create_notification(
                        user_doc["id"],
                        "premium",
                        "🎉 Bienvenue dans Premium !",
                        "Tu as maintenant accès aux paires illimitées, prédictions illimitées et trading Live.",
                    )
                elif etype == "customer.subscription.deleted":
                    await _create_notification(
                        user_doc["id"],
                        "premium",
                        "❌ Abonnement Premium annulé",
                        "Tu repasses en plan Free. Tu peux te réabonner à tout moment.",
                    )
        elif etype == "invoice.payment_failed":
            if user_doc:
                await db.users.update_one(
                    {"id": user_doc["id"]},
                    {"$set": {"subscription_status": "past_due"}},
                )
                await _create_notification(
                    user_doc["id"],
                    "premium",
                    "⚠️ Paiement Premium échoué",
                    "Le paiement de ton abonnement Premium n'a pas pu être traité. Mets à jour ta carte sur Stripe.",
                )
        elif etype == "checkout.session.completed":
            # Initial activation; the subscription.created event will set details
            logger.info(f"Stripe checkout completed for customer={customer_id}")
    except Exception as e:
        logger.exception(f"Stripe webhook handler error: {e}")
    return {"received": True}


class BotConfig(BaseModel):
    user_id: str
    enabled: bool = False
    mode: str = "paper"  # paper / live (live not implemented yet)
    strategy: str = "hybrid"  # indicators / hybrid
    capital_usdt: float = 1000.0
    paper_balance_usdt: float = 1000.0
    max_positions: int = 5
    position_size_pct: float = 25.0  # % of capital per trade
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 10.0
    interval_minutes: int = 5
    trailing_enabled: bool = True
    trailing_trigger_pct: float = 3.0  # activate trailing once profit reaches this
    trailing_distance_pct: float = 2.0  # SL trails this far below highest price
    compounding_enabled: bool = True  # capital grows with realized profits
    ai_predictions_enabled: bool = True  # use AI predictions for entries + exits
    ai_exit_confidence: int = 65  # min confidence for AI to trigger an early exit
    # ----- LIVE TRADING -----
    live_mode: bool = False  # false = paper trading, true = real Binance orders
    live_max_position_usdt: float = 50.0  # SAFETY cap: max USDT per single order in live mode
    live_killswitch: bool = False  # if true → only close positions, NEVER open new ones
    pairs: List[str] = Field(default_factory=lambda: DEFAULT_BOT_PAIRS.copy())
    last_run_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BotConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    capital_usdt: Optional[float] = None
    max_positions: Optional[int] = None
    position_size_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    interval_minutes: Optional[int] = None
    pairs: Optional[List[str]] = None
    strategy: Optional[str] = None
    trailing_enabled: Optional[bool] = None
    trailing_trigger_pct: Optional[float] = None
    trailing_distance_pct: Optional[float] = None
    compounding_enabled: Optional[bool] = None
    ai_predictions_enabled: Optional[bool] = None
    ai_exit_confidence: Optional[int] = None
    live_mode: Optional[bool] = None
    live_max_position_usdt: Optional[float] = None
    live_killswitch: Optional[bool] = None


class BotPosition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    side: str = "long"
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    original_stop_loss: float = 0.0  # initial SL for reference
    highest_price: float = 0.0  # tracked since entry, for trailing
    trail_active: bool = False  # true once trailing has been triggered
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entry_reason: str = ""
    ai_target_median: Optional[float] = None  # AI-predicted target if available
    last_ai_check: Optional[datetime] = None  # last prediction sanity-check
    status: str = "open"  # open / closed


class BotTrade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pnl: float
    pnl_pct: float
    exit_reason: str  # take_profit / stop_loss / signal_reverse / manual


async def _get_or_create_bot_config(user_id: str) -> dict:
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0})
    if not cfg:
        cfg_obj = BotConfig(user_id=user_id)
        await db.bot_configs.insert_one(cfg_obj.dict())
        cfg = cfg_obj.dict()
    return cfg


@api_router.get("/bot/config")
async def bot_get_config(user=Depends(get_current_user)):
    return await _get_or_create_bot_config(user["id"])


@api_router.put("/bot/config")
async def bot_update_config(req: BotConfigUpdate, user=Depends(get_current_user)):
    await _get_or_create_bot_config(user["id"])
    update = {k: v for k, v in req.dict().items() if v is not None}
    if not update:
        cfg = await db.bot_configs.find_one({"user_id": user["id"]}, {"_id": 0})
        return cfg
    # validation
    if "stop_loss_pct" in update and (update["stop_loss_pct"] <= 0 or update["stop_loss_pct"] > 50):
        raise HTTPException(status_code=400, detail="Stop-loss doit être entre 0.1% et 50%")
    if "take_profit_pct" in update and (update["take_profit_pct"] <= 0 or update["take_profit_pct"] > 100):
        raise HTTPException(status_code=400, detail="Take-profit doit être entre 0.1% et 100%")
    if "position_size_pct" in update and (update["position_size_pct"] <= 0 or update["position_size_pct"] > 100):
        raise HTTPException(status_code=400, detail="Taille position invalide (1-100%)")
    if "max_positions" in update and (update["max_positions"] < 1 or update["max_positions"] > 10):
        raise HTTPException(status_code=400, detail="max_positions doit être entre 1 et 10")
    if "capital_usdt" in update and update["capital_usdt"] <= 0:
        raise HTTPException(status_code=400, detail="Capital invalide")
    # Live mode requires Binance keys connected
    if update.get("live_mode") is True:
        u = await db.users.find_one({"id": user["id"]})
        if not u or not u.get("binance_api_key_enc"):
            raise HTTPException(
                status_code=400,
                detail="Connecte d'abord tes clés Binance avant d'activer le mode Live",
            )
        # Live mode is Premium-only
        premium = await _get_premium_status(user["id"])
        if not premium["is_premium"]:
            raise HTTPException(
                status_code=402,
                detail="Le trading LIVE est réservé aux membres Premium. Passe à Premium pour l'activer (9,99€/mois).",
            )
    # Free tier: max 3 pairs
    if "pairs" in update and update["pairs"] is not None:
        premium = await _get_premium_status(user["id"])
        if not premium["is_premium"] and len(update["pairs"]) > FREE_MAX_PAIRS:
            raise HTTPException(
                status_code=402,
                detail=f"Plan Free limité à {FREE_MAX_PAIRS} paires. Passe à Premium pour des paires illimitées.",
            )

    await db.bot_configs.update_one({"user_id": user["id"]}, {"$set": update})
    cfg = await db.bot_configs.find_one({"user_id": user["id"]}, {"_id": 0})
    return cfg


@api_router.post("/bot/reset")
async def bot_reset(user=Depends(get_current_user)):
    """Reset paper portfolio: close all positions, reset balance."""
    cfg = await _get_or_create_bot_config(user["id"])
    await db.bot_positions.delete_many({"user_id": user["id"]})
    await db.bot_trades.delete_many({"user_id": user["id"]})
    await db.bot_configs.update_one(
        {"user_id": user["id"]},
        {"$set": {"paper_balance_usdt": cfg.get("capital_usdt", 1000.0), "enabled": False}},
    )
    return {"ok": True}


@api_router.get("/bot/positions")
async def bot_get_positions(user=Depends(get_current_user)):
    cur = db.bot_positions.find({"user_id": user["id"], "status": "open"}, {"_id": 0}).sort("entry_time", -1)
    positions = await cur.to_list(50)
    if not positions:
        return []
    # enrich with current prices
    symbols = list({p["symbol"] for p in positions})
    prices = {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            )
            if r.status_code == 200:
                prices = {x["symbol"]: float(x["price"]) for x in r.json()}
    except Exception:
        pass
    out = []
    for p in positions:
        cp = prices.get(p["symbol"], p["entry_price"])
        invested = p["entry_price"] * p["quantity"]
        cur_val = cp * p["quantity"]
        pnl = cur_val - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        out.append({
            **p,
            "current_price": cp,
            "current_value": cur_val,
            "invested": invested,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
    return out


@api_router.get("/bot/trades")
async def bot_get_trades(user=Depends(get_current_user), limit: int = 50):
    cur = db.bot_trades.find({"user_id": user["id"]}, {"_id": 0}).sort("exit_time", -1).limit(limit)
    return await cur.to_list(limit)


@api_router.get("/bot/stats")
async def bot_get_stats(user=Depends(get_current_user)):
    cfg = await _get_or_create_bot_config(user["id"])
    trades = await db.bot_trades.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    open_positions = await db.bot_positions.find(
        {"user_id": user["id"], "status": "open"}, {"_id": 0}
    ).to_list(50)

    total_pnl = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0

    # unrealized pnl on open positions
    unrealized = 0.0
    if open_positions:
        symbols = list({p["symbol"] for p in open_positions})
        try:
            async with httpx.AsyncClient(timeout=8.0) as cli:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/ticker/price",
                    params={"symbols": json.dumps(symbols, separators=(",", ":"))},
                )
                if r.status_code == 200:
                    prices = {x["symbol"]: float(x["price"]) for x in r.json()}
                    for p in open_positions:
                        cp = prices.get(p["symbol"], p["entry_price"])
                        unrealized += (cp - p["entry_price"]) * p["quantity"]
        except Exception:
            pass

    return {
        "enabled": cfg.get("enabled", False),
        "paper_balance_usdt": cfg.get("paper_balance_usdt", cfg.get("capital_usdt", 1000.0)),
        "capital_usdt": cfg.get("capital_usdt", 1000.0),
        "total_realized_pnl": total_pnl,
        "unrealized_pnl": unrealized,
        "total_pnl": total_pnl + unrealized,
        "trades_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "open_positions_count": len(open_positions),
        "last_run_at": cfg.get("last_run_at"),
    }


@api_router.post("/bot/run-now")
async def bot_run_now(user=Depends(get_current_user)):
    """Force an immediate bot evaluation (manual trigger)."""
    cfg = await _get_or_create_bot_config(user["id"])
    if not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="Active le bot d'abord")
    await _bot_check_positions(user["id"])
    await _bot_evaluate_entries(user["id"], cfg)
    await db.bot_configs.update_one(
        {"user_id": user["id"]}, {"$set": {"last_run_at": datetime.now(timezone.utc)}}
    )
    return {"ok": True}


class BacktestReq(BaseModel):
    days: int = 30
    capital_usdt: float = 1000.0
    position_size_pct: float = 20.0
    max_positions: int = 3
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 5.0
    pairs: List[str] = Field(default_factory=lambda: DEFAULT_BOT_PAIRS.copy())
    interval: str = "1h"


@api_router.post("/bot/backtest")
async def bot_backtest(req: BacktestReq, user=Depends(get_current_user)):
    """Simulate bot strategy on historical Binance data. Pure indicators (no LLM for speed)."""
    if req.days < 1 or req.days > 90:
        raise HTTPException(status_code=400, detail="Période entre 1 et 90 jours")
    if not req.pairs:
        raise HTTPException(status_code=400, detail="Aucune paire sélectionnée")

    # kline interval to seconds
    interval_sec = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(req.interval, 3600)
    candles_per_day = 86400 // interval_sec
    limit = min(1000, req.days * candles_per_day + 60)  # +60 for indicator warmup

    # Fetch historical klines for each pair in parallel
    histories: dict = {}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        async def fetch_one(sym):
            try:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={"symbol": sym, "interval": req.interval, "limit": limit},
                )
                if r.status_code != 200:
                    return sym, None
                return sym, r.json()
            except Exception as e:
                logger.warning(f"Backtest kline error {sym}: {e}")
                return sym, None

        results = await asyncio.gather(*[fetch_one(s) for s in req.pairs])
        for sym, kl in results:
            if kl:
                histories[sym] = kl

    if not histories:
        raise HTTPException(status_code=502, detail="Données historiques indisponibles")

    # All pairs should have same timeline roughly. Use min length.
    N = min(len(kl) for kl in histories.values())
    if N < 50:
        raise HTTPException(status_code=400, detail="Historique insuffisant")

    # State
    balance = req.capital_usdt
    trade_size = req.capital_usdt * (req.position_size_pct / 100.0)
    open_positions: dict = {}  # symbol -> {entry, qty, sl, tp, entry_time}
    trades: List[dict] = []
    equity_curve = []  # list of {t, equity}

    # Iterate candles
    warmup = 30
    for i in range(warmup, N):
        ts = histories[list(histories.keys())[0]][i][0]  # openTime of current candle

        # 1) Check open positions with current candle's high/low
        to_close = []
        for sym, pos in open_positions.items():
            kl_i = histories[sym][i]
            high = float(kl_i[2])
            low = float(kl_i[3])
            close_p = float(kl_i[4])
            # check SL first (conservative: if both hit in same candle, SL wins)
            if low <= pos["sl"]:
                exit_px = pos["sl"]
                reason = "stop_loss"
            elif high >= pos["tp"]:
                exit_px = pos["tp"]
                reason = "take_profit"
            else:
                continue
            invested = pos["entry"] * pos["qty"]
            exit_val = exit_px * pos["qty"]
            pnl = exit_val - invested
            pnl_pct = (pnl / invested) * 100 if invested else 0
            trades.append({
                "symbol": sym,
                "entry_price": pos["entry"],
                "exit_price": exit_px,
                "quantity": pos["qty"],
                "entry_time": pos["entry_time"],
                "exit_time": ts,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": reason,
            })
            balance += exit_val
            to_close.append(sym)
        for sym in to_close:
            del open_positions[sym]

        # 2) Evaluate new entries
        if len(open_positions) < req.max_positions and balance >= trade_size:
            best = None
            for sym, kl in histories.items():
                if sym in open_positions:
                    continue
                closes = [float(k[4]) for k in kl[: i + 1]]
                if len(closes) < 30:
                    continue
                rsi = compute_rsi(closes, 14) or 50
                ema12 = compute_ema(closes, 12)
                ema26 = compute_ema(closes, 26)
                if not ema12 or not ema26:
                    continue
                bullish = ema12 > ema26
                last = closes[-1]
                prev = closes[-2]
                action = None
                strength = 0
                if bullish and rsi < 40 and last > prev:
                    action = "BUY"
                    strength = min(100, (40 - rsi) * 3 + 50)
                elif bullish and 40 <= rsi < 55 and last > prev:
                    action = "BUY"
                    strength = 60
                if action == "BUY" and strength >= 55:
                    if best is None or strength > best["strength"]:
                        best = {"symbol": sym, "strength": strength, "price": last}

            if best and balance >= trade_size:
                entry = best["price"]
                qty = trade_size / entry
                sl = entry * (1 - req.stop_loss_pct / 100)
                tp = entry * (1 + req.take_profit_pct / 100)
                open_positions[best["symbol"]] = {
                    "entry": entry,
                    "qty": qty,
                    "sl": sl,
                    "tp": tp,
                    "entry_time": ts,
                }
                balance -= trade_size

        # 3) Snapshot equity (balance + value of open positions at close price)
        unreal = 0.0
        for sym, pos in open_positions.items():
            cur = float(histories[sym][i][4])
            unreal += cur * pos["qty"]
        eq = balance + unreal
        if i % max(1, N // 80) == 0:  # ~80 points on curve
            equity_curve.append({"t": ts, "equity": eq})

    # Close remaining positions at last close
    last_i = N - 1
    for sym, pos in list(open_positions.items()):
        close_p = float(histories[sym][last_i][4])
        invested = pos["entry"] * pos["qty"]
        exit_val = close_p * pos["qty"]
        pnl = exit_val - invested
        pnl_pct = (pnl / invested) * 100 if invested else 0
        trades.append({
            "symbol": sym,
            "entry_price": pos["entry"],
            "exit_price": close_p,
            "quantity": pos["qty"],
            "entry_time": pos["entry_time"],
            "exit_time": histories[sym][last_i][0],
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": "period_end",
        })
        balance += exit_val
    open_positions.clear()

    total_pnl = balance - req.capital_usdt
    total_pnl_pct = (total_pnl / req.capital_usdt) * 100 if req.capital_usdt else 0
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    avg_win = (sum(t["pnl"] for t in wins) / len(wins)) if wins else 0
    avg_loss = (sum(t["pnl"] for t in losses) / len(losses)) if losses else 0
    best_trade = max(trades, key=lambda t: t["pnl"]) if trades else None
    worst_trade = min(trades, key=lambda t: t["pnl"]) if trades else None

    # compute buy&hold comparison (avg of pairs)
    bh_returns = []
    for sym, kl in histories.items():
        if len(kl) >= warmup + 1:
            first = float(kl[warmup][4])
            last = float(kl[-1][4])
            bh_returns.append((last - first) / first * 100)
    bh_avg = sum(bh_returns) / len(bh_returns) if bh_returns else 0

    return {
        "period_days": req.days,
        "capital_start": req.capital_usdt,
        "capital_end": balance,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "trades_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "buy_hold_pct": bh_avg,
        "outperformance_pct": total_pnl_pct - bh_avg,
        "equity_curve": equity_curve,
        "trades": trades[-30:],  # return last 30 trades only
    }


# ----- Bot engine -----
async def _eval_signal(closes: List[float], highs: List[float], lows: List[float]) -> dict:
    """Quick technical signal: returns action / strength / reason."""
    if len(closes) < 30:
        return {"action": "HOLD", "strength": 0, "reason": "données insuffisantes", "rsi": None}
    rsi = compute_rsi(closes, 14) or 50
    ema12 = compute_ema(closes, 12)
    ema26 = compute_ema(closes, 26)
    last = closes[-1]
    prev = closes[-2]
    if not ema12 or not ema26:
        return {"action": "HOLD", "strength": 0, "reason": "EMA insuffisant", "rsi": rsi}

    # bullish trend + oversold bounce
    bullish = ema12 > ema26
    bearish = ema12 < ema26

    action = "HOLD"
    strength = 0
    reason = ""

    if bullish and rsi < 40 and last > prev:
        action = "BUY"
        strength = int(min(100, (40 - rsi) * 3 + 50))
        reason = f"Tendance haussière (EMA12>EMA26) + RSI bas {rsi:.0f} = rebond probable"
    elif bullish and 40 <= rsi < 55 and last > prev:
        action = "BUY"
        strength = 60
        reason = f"Reprise haussière confirmée (RSI {rsi:.0f}, prix>prix-1)"
    elif bearish and rsi > 65:
        action = "SELL"
        strength = int(min(100, (rsi - 65) * 3 + 50))
        reason = f"Tendance baissière + RSI surachat {rsi:.0f}"

    return {"action": action, "strength": strength, "reason": reason, "rsi": rsi, "ema12": ema12, "ema26": ema26}


async def _claude_validate(symbol: str, interval: str, indicators: dict, signal: dict) -> dict:
    """Ask Claude to validate a candidate trade. Returns {'approved': bool, 'reason': str}."""
    try:
        system_msg = (
            "Tu es un trader algorithmique pragmatique en paper trading (test, pas d'argent réel). "
            "Tu reçois un signal d'achat technique déjà filtré (RSI + EMA). Ton job: APPROUVER par défaut "
            "sauf si tu vois un risque évident (forte volatilité baissière, retournement clair, news négative). "
            "Sois constructif, on apprend de chaque trade en paper. "
            "Réponds STRICTEMENT en JSON: {\"approved\": true|false, \"reason\": \"explication courte FR (1 phrase)\"}."
        )
        user_text = (
            f"Symbole: {symbol} ({interval})\nSignal: {signal['action']} (force {signal['strength']}%)\n"
            f"Logique: {signal['reason']}\n"
            f"RSI={indicators.get('rsi14') or signal.get('rsi'):.1f} "
            f"EMA12={indicators.get('ema12') or signal.get('ema12'):.4f} "
            f"EMA26={indicators.get('ema26') or signal.get('ema26'):.4f}\n"
            f"Approuves-tu ?"
        )
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"botval-{symbol}-{int(datetime.now(timezone.utc).timestamp())}",
            system_message=system_msg,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=user_text))
        cleaned = resp.strip().strip("`").lstrip("json").strip()
        parsed = json.loads(cleaned)
        return {"approved": bool(parsed.get("approved", True)), "reason": str(parsed.get("reason", ""))}
    except Exception as e:
        logger.warning(f"Claude validation failed: {e}")
        # fallback: approve if signal strength >= 55 to avoid blocking the bot when LLM unavailable
        return {"approved": signal.get("strength", 0) >= 55, "reason": "Validation IA indisponible — règle technique appliquée"}


async def _close_position(user_id: str, position: dict, exit_price: float, reason: str):
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0}) or {}
    is_live = bool(cfg.get("live_mode")) and not position.get("paper", False)
    live_order_id = None

    # If LIVE mode → place a real MARKET SELL on Binance first
    if is_live:
        bcli = await _get_user_binance(user_id)
        if bcli:
            try:
                # Round qty DOWN to lot step
                step = float(position.get("lot_step", 0)) or 0
                qty_to_sell = round_step(float(position["quantity"]), step) if step > 0 else float(position["quantity"])
                if qty_to_sell <= 0:
                    raise RuntimeError("Quantité après arrondi = 0")
                order = await bcli.market_sell(position["symbol"], qty_to_sell)
                ex = extract_executed(order)
                if ex["avg_price"] > 0:
                    exit_price = ex["avg_price"]
                live_order_id = order.get("orderId")
                logger.info(
                    f"BOT LIVE SELL {position['symbol']} qty={qty_to_sell} avg={ex['avg_price']:.6f} order={live_order_id}"
                )
            except Exception as e:
                logger.exception(f"LIVE SELL FAILED {position['symbol']}: {e}")
                # Notify the user but still close the position in paper db
                await _create_notification(
                    user_id,
                    "live_error",
                    f"⚠️ Sortie LIVE échouée {symbolToBase_py(position['symbol'])}",
                    f"Erreur Binance : {str(e)[:120]}. Position fermée en simulation.",
                    {"symbol": position["symbol"], "error": str(e)[:200]},
                )
                is_live = False  # fallback to paper bookkeeping

    invested = position["entry_price"] * position["quantity"]
    exit_val = exit_price * position["quantity"]
    pnl = exit_val - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    trade = BotTrade(
        user_id=user_id,
        symbol=position["symbol"],
        side=position["side"],
        quantity=position["quantity"],
        entry_price=position["entry_price"],
        exit_price=exit_price,
        entry_time=position["entry_time"],
        pnl=pnl,
        pnl_pct=pnl_pct,
        exit_reason=reason,
    )
    trade_dict = trade.dict()
    trade_dict["live"] = is_live
    if live_order_id:
        trade_dict["live_order_id"] = live_order_id
    await db.bot_trades.insert_one(trade_dict)
    await db.bot_positions.update_one(
        {"id": position["id"]}, {"$set": {"status": "closed"}}
    )
    # Paper bookkeeping (we always track paper balance even in live mode, for stats)
    update = {"$inc": {"paper_balance_usdt": exit_val}}
    if cfg.get("compounding_enabled", True):
        update["$inc"]["capital_usdt"] = pnl  # capital grows by realized pnl
    await db.bot_configs.update_one({"user_id": user_id}, update)
    live_tag = " [LIVE]" if is_live else ""
    logger.info(f"BOT CLOSE{live_tag} {position['symbol']} pnl={pnl:.2f} ({pnl_pct:.2f}%) reason={reason}")

    # Send notification
    sym = symbolToBase_py(position["symbol"])
    is_win = pnl > 0
    icon = "🎉" if is_win and reason == "take_profit" else "🛡️" if is_win and "trail" in reason else "🔮" if reason == "ai_exit_baisse" else "✅" if is_win else "❌"
    reason_fr = {
        "take_profit": "Take-Profit atteint",
        "stop_loss": "Stop-Loss déclenché",
        "trailing_stop": "Trailing SL — gain verrouillé",
        "ai_exit_baisse": "Sortie IA — baisse anticipée",
    }.get(reason, reason)
    title = f"{icon} {sym} fermé : {pnl:+.2f} $"
    body = f"{reason_fr} · PnL {pnl_pct:+.2f}% · Sortie à ${exit_price:.4f}"
    await _create_notification(
        user_id,
        "trade_close",
        title,
        body,
        {"symbol": position["symbol"], "pnl": pnl, "pnl_pct": pnl_pct, "reason": reason},
    )


def symbolToBase_py(sym: str) -> str:
    return sym.replace("USDT", "").replace("BUSD", "").replace("USD", "")


async def _bot_check_positions(user_id: str):
    """Check open positions: trailing SL update + SL/TP exit."""
    open_pos = await db.bot_positions.find(
        {"user_id": user_id, "status": "open"}, {"_id": 0}
    ).to_list(50)
    if not open_pos:
        return
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0}) or {}
    trailing_enabled = cfg.get("trailing_enabled", True)
    trail_trigger = cfg.get("trailing_trigger_pct", 3.0)
    trail_dist = cfg.get("trailing_distance_pct", 2.0)

    symbols = list({p["symbol"] for p in open_pos})
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            )
            r.raise_for_status()
            prices = {x["symbol"]: float(x["price"]) for x in r.json()}
    except Exception as e:
        logger.warning(f"Bot check prices error: {e}")
        return

    for p in open_pos:
        cp = prices.get(p["symbol"])
        if not cp:
            continue

        # Update highest price + trailing SL
        if trailing_enabled:
            highest = max(p.get("highest_price", 0) or p["entry_price"], cp)
            new_sl = p["stop_loss"]
            trail_active = p.get("trail_active", False)
            profit_pct = (cp - p["entry_price"]) / p["entry_price"] * 100

            update_fields = {}
            if highest > (p.get("highest_price") or 0):
                update_fields["highest_price"] = highest

            if profit_pct >= trail_trigger:
                # candidate SL = highest * (1 - trail_dist%)
                candidate_sl = highest * (1 - trail_dist / 100)
                # only raise SL upward, never lower it
                if candidate_sl > p["stop_loss"]:
                    new_sl = candidate_sl
                    update_fields["stop_loss"] = new_sl
                    if not trail_active:
                        update_fields["trail_active"] = True
                        logger.info(
                            f"BOT TRAIL ACTIVATED {p['symbol']} entry={p['entry_price']:.4f} "
                            f"price={cp:.4f} new_SL={new_sl:.4f} (was {p['stop_loss']:.4f})"
                        )
            if update_fields:
                await db.bot_positions.update_one({"id": p["id"]}, {"$set": update_fields})
                p["stop_loss"] = update_fields.get("stop_loss", p["stop_loss"])

        # Check exit
        if cp <= p["stop_loss"]:
            reason = "trailing_stop" if p.get("trail_active") else "stop_loss"
            await _close_position(user_id, p, cp, reason)
            continue
        elif cp >= p["take_profit"]:
            await _close_position(user_id, p, cp, "take_profit")
            continue

        # AI-driven early exit: check prediction every 30 min per position
        if cfg.get("ai_predictions_enabled", True):
            last_ai = p.get("last_ai_check")
            should_check = True
            if last_ai:
                if last_ai.tzinfo is None:
                    last_ai = last_ai.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_ai).total_seconds() < 30 * 60:
                    should_check = False
            if should_check:
                pred = await _fetch_or_compute_prediction(p["symbol"], "24h")
                await db.bot_positions.update_one(
                    {"id": p["id"]}, {"$set": {"last_ai_check": datetime.now(timezone.utc)}}
                )
                if pred:
                    profit_pct = (cp - p["entry_price"]) / p["entry_price"] * 100
                    threshold = cfg.get("ai_exit_confidence", 65)
                    if pred["direction"] == "BAISSE" and pred["confidence"] >= threshold and profit_pct > 0:
                        # Lock the profit before AI-predicted drop
                        logger.info(
                            f"BOT AI_EXIT {p['symbol']} prediction BAISSE conf={pred['confidence']}% "
                            f"profit={profit_pct:.2f}% — closing to lock gains"
                        )
                        await _close_position(user_id, p, cp, "ai_exit_baisse")


async def _bot_evaluate_entries(user_id: str, cfg: dict):
    """Look for new entries on configured pairs."""
    # KILL-SWITCH (live mode): if engaged, refuse to open new positions
    if cfg.get("live_mode") and cfg.get("live_killswitch"):
        logger.info(f"BOT KILL-SWITCH on for user={user_id[:8]}, no new entries")
        return
    open_pos = await db.bot_positions.find(
        {"user_id": user_id, "status": "open"}, {"_id": 0}
    ).to_list(50)
    if len(open_pos) >= cfg["max_positions"]:
        return
    open_syms = {p["symbol"] for p in open_pos}
    pairs = [s for s in cfg.get("pairs", DEFAULT_BOT_PAIRS) if s not in open_syms]

    cfg_now = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0})
    balance = cfg_now.get("paper_balance_usdt", cfg["capital_usdt"])
    capital = cfg_now.get("capital_usdt", 1000.0)
    size_pct = cfg_now.get("position_size_pct", 20.0)
    trade_size = capital * (size_pct / 100.0)
    if balance < trade_size:
        return  # not enough paper cash

    candidates = []
    async with httpx.AsyncClient(timeout=10.0) as cli:
        for sym in pairs:
            try:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={"symbol": sym, "interval": "15m", "limit": 100},
                )
                if r.status_code != 200:
                    continue
                kl = r.json()
                closes = [float(k[4]) for k in kl]
                highs = [float(k[2]) for k in kl]
                lows = [float(k[3]) for k in kl]
                sig = await _eval_signal(closes, highs, lows)
                if sig["action"] == "BUY" and sig["strength"] >= 50:
                    candidates.append({
                        "symbol": sym,
                        "signal": sig,
                        "last_price": closes[-1],
                    })
            except Exception as e:
                logger.warning(f"Bot kline error {sym}: {e}")

    # take strongest candidate first
    candidates.sort(key=lambda c: c["signal"]["strength"], reverse=True)
    available_slots = cfg["max_positions"] - len(open_pos)
    logger.info(
        f"BOT SCAN user={user_id[:8]} candidates={len(candidates)} "
        f"slots={available_slots} balance={balance:.2f} "
        f"top={[(c['symbol'], c['signal']['action'], c['signal']['strength']) for c in candidates[:3]]}"
    )

    for c in candidates[:available_slots]:
        # build indicators dict for Claude
        indicators = {
            "lastPrice": c["last_price"],
            "rsi14": c["signal"].get("rsi"),
            "ema12": c["signal"].get("ema12"),
            "ema26": c["signal"].get("ema26"),
        }
        # Hybrid mode: validate with Claude only for medium-strength signals
        approve = True
        validation_reason = ""
        if cfg.get("strategy") == "hybrid" and c["signal"]["strength"] < 70:
            v = await _claude_validate(c["symbol"], "15m", indicators, c["signal"])
            approve = v["approved"]
            validation_reason = v["reason"]
        if not approve:
            logger.info(f"BOT REJECTED {c['symbol']} by Claude: {validation_reason}")
            continue

        # AI-prediction guard (NEW): require HAUSSE direction to proceed
        ai_target = None
        ai_reason_extra = ""
        if cfg_now.get("ai_predictions_enabled", True):
            pred = await _fetch_or_compute_prediction(c["symbol"], "24h")
            if pred:
                if pred["direction"] == "BAISSE":
                    logger.info(
                        f"BOT AI_REJECTED {c['symbol']} prediction BAISSE conf={pred['confidence']}%"
                    )
                    continue
                if pred["direction"] == "STABLE" and pred["confidence"] >= 70:
                    # Strong stable prediction = skip (no upside)
                    logger.info(f"BOT AI_REJECTED {c['symbol']} prediction STABLE high-conf")
                    continue
                # HAUSSE or weak STABLE → proceed and use AI target
                if pred["direction"] == "HAUSSE":
                    ai_target = pred.get("target_median")
                    ai_reason_extra = f" | 🔮 IA prédit HAUSSE conf {pred['confidence']}%"

        cfg_now = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0})
        balance = cfg_now.get("paper_balance_usdt", 0)
        if balance < trade_size:
            break
        entry = c["last_price"]

        # Determine if this position will be LIVE (real Binance order) or PAPER
        is_live = bool(cfg_now.get("live_mode"))
        bcli = None
        lot_step = 0.0
        if is_live:
            bcli = await _get_user_binance(user_id)
            if not bcli:
                logger.warning(f"BOT LIVE off: no Binance client for user={user_id[:8]}")
                is_live = False

        if is_live:
            # SAFETY cap (live_max_position_usdt)
            live_cap = float(cfg_now.get("live_max_position_usdt", 50.0))
            live_trade = min(trade_size, live_cap)
            try:
                # Fetch symbol filters once for LOT_SIZE step
                sinfo = await bcli.get_symbol_info(c["symbol"])
                step = 0.0
                min_notional = 10.0
                for f in sinfo.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        step = float(f.get("stepSize", 0))
                    elif f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL"):
                        try:
                            min_notional = float(f.get("minNotional") or f.get("notional", 10))
                        except Exception:
                            pass
                lot_step = step
                if live_trade < min_notional:
                    logger.info(f"BOT LIVE skip {c['symbol']}: notional {live_trade:.2f} < min {min_notional}")
                    continue
                order = await bcli.market_buy_quote(c["symbol"], live_trade)
                ex = extract_executed(order)
                if ex["qty"] <= 0 or ex["avg_price"] <= 0:
                    raise RuntimeError("Ordre rempli partiellement ou prix nul")
                entry = ex["avg_price"]
                qty = round_step(ex["qty"], step) if step > 0 else ex["qty"]
                trade_size = ex["quote"]
                logger.info(
                    f"BOT LIVE BUY {c['symbol']} quote={live_trade:.2f} -> qty={qty} @ {entry:.6f} order={order.get('orderId')}"
                )
                await _create_notification(
                    user_id,
                    "live_buy",
                    f"💸 Achat LIVE : {symbolToBase_py(c['symbol'])}",
                    f"Acheté ${ex['quote']:.2f} @ ${entry:.4f} sur Binance",
                    {"symbol": c["symbol"], "entry": entry, "qty": qty, "live": True},
                )
            except Exception as e:
                logger.exception(f"BOT LIVE BUY failed {c['symbol']}: {e}")
                await _create_notification(
                    user_id,
                    "live_error",
                    f"⚠️ Achat LIVE échoué : {symbolToBase_py(c['symbol'])}",
                    f"Erreur Binance : {str(e)[:120]}",
                    {"symbol": c["symbol"], "error": str(e)[:200]},
                )
                continue  # do not open paper position when live mode active and order failed
        else:
            qty = trade_size / entry

        sl = entry * (1 - cfg_now["stop_loss_pct"] / 100)
        fixed_tp = entry * (1 + cfg_now["take_profit_pct"] / 100)
        # Dynamic TP: if AI target is higher than fixed TP, use AI target (let AI prediction guide profit-taking)
        if ai_target and ai_target > fixed_tp:
            tp = ai_target
            tp_source = f"IA: ${ai_target:.4f}"
        else:
            tp = fixed_tp
            tp_source = "fixe"

        pos = BotPosition(
            user_id=user_id,
            symbol=c["symbol"],
            quantity=qty,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            original_stop_loss=sl,
            highest_price=entry,
            ai_target_median=ai_target,
            entry_reason=f"{c['signal']['reason']} | IA: {validation_reason}{ai_reason_extra} | TP {tp_source}".strip(" |"),
        )
        pos_dict = pos.dict()
        pos_dict["live"] = is_live
        pos_dict["lot_step"] = lot_step
        await db.bot_positions.insert_one(pos_dict)
        await db.bot_configs.update_one(
            {"user_id": user_id},
            {"$inc": {"paper_balance_usdt": -trade_size}},
        )
        live_tag = " [LIVE]" if is_live else ""
        logger.info(f"BOT OPEN{live_tag} {c['symbol']} @ {entry} qty={qty:.6f} SL={sl:.4f} TP={tp:.4f} ({tp_source}) strength={c['signal']['strength']}")

        # Notify (skip if already notified for live)
        if not is_live:
            sym_base = symbolToBase_py(c["symbol"])
            await _create_notification(
                user_id,
                "trade_open",
                f"🚀 Position ouverte : {sym_base}",
                f"Entrée ${entry:.4f} · TP ${tp:.4f} · {trade_size:.0f} $ engagés",
                {"symbol": c["symbol"], "entry": entry, "tp": tp, "sl": sl},
            )


async def _bot_loop():
    logger.info("Bot engine loop started")
    await asyncio.sleep(15)  # let app boot
    while True:
        try:
            now = datetime.now(timezone.utc)
            cfgs = await db.bot_configs.find({"enabled": True}, {"_id": 0}).to_list(500)
            for cfg in cfgs:
                try:
                    user_id = cfg["user_id"]
                    # always check SL/TP
                    await _bot_check_positions(user_id)
                    # only evaluate new entries every interval_minutes
                    last_run = cfg.get("last_run_at")
                    interval = cfg.get("interval_minutes", 5)
                    should_run = (
                        not last_run
                        or (now - last_run.replace(tzinfo=timezone.utc) if last_run.tzinfo is None else now - last_run)
                        >= timedelta(minutes=interval)
                    )
                    if should_run:
                        await _bot_evaluate_entries(user_id, cfg)
                        await db.bot_configs.update_one(
                            {"user_id": user_id}, {"$set": {"last_run_at": now}}
                        )
                except Exception as e:
                    logger.exception(f"Bot loop user error: {e}")
        except Exception as e:
            logger.exception(f"Bot loop error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _start_bot():
    asyncio.create_task(_bot_loop())


class PredictReq(BaseModel):
    symbol: str
    horizon: str = "24h"  # 24h / 3d / 7d


@api_router.post("/ai/predict")
async def ai_predict(req: PredictReq, user=Depends(get_current_user)):
    # Free tier rate-limit: FREE_MAX_PREDICTIONS_PER_DAY per UTC day
    premium = await _get_premium_status(user["id"])
    if not premium["is_premium"]:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        used = await db.prediction_quota.count_documents({
            "user_id": user["id"],
            "ts": {"$gte": today_start},
        })
        if used >= FREE_MAX_PREDICTIONS_PER_DAY:
            raise HTTPException(
                status_code=402,
                detail=f"Plan Free limité à {FREE_MAX_PREDICTIONS_PER_DAY} prédiction(s) IA par jour. Passe à Premium pour des prédictions illimitées.",
            )
        # Record usage (only for Free users)
        await db.prediction_quota.insert_one({
            "user_id": user["id"],
            "ts": datetime.now(timezone.utc),
            "symbol": req.symbol.upper(),
            "horizon": req.horizon,
        })
    symbol = req.symbol.upper()
    horizon = req.horizon
    interval_map = {"24h": "1h", "3d": "4h", "7d": "1d"}
    candles_map = {"24h": 100, "3d": 100, "7d": 60}
    interval = interval_map.get(horizon, "1h")
    limit = candles_map.get(horizon, 100)

    # Check cache (1h)
    cache_key = f"predict:{symbol}:{horizon}"
    cached = await db.predictions.find_one(
        {"key": cache_key},
        {"_id": 0, "key": 0},
    )
    if cached:
        gen = cached.get("generated_at")
        if gen:
            if gen.tzinfo is None:
                gen = gen.replace(tzinfo=timezone.utc)
            age_min = (datetime.now(timezone.utc) - gen).total_seconds() / 60
            if age_min < 60:
                cached["cached"] = True
                cached["cached_age_min"] = int(age_min)
                return cached

    async with httpx.AsyncClient(timeout=12.0) as cli:
        try:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Predict klines error: {e}")
            raise HTTPException(status_code=502, detail="Données indisponibles")

    closes = [float(k[4]) for k in data]
    highs = [float(k[2]) for k in data]
    lows = [float(k[3]) for k in data]
    vols = [float(k[5]) for k in data]
    last = closes[-1]
    rsi = compute_rsi(closes, 14) or 50
    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    ema12 = compute_ema(closes, 12)
    ema26 = compute_ema(closes, 26)
    period_high = max(highs[-30:])
    period_low = min(lows[-30:])
    change_24h = (closes[-1] - closes[-24]) / closes[-24] * 100 if len(closes) >= 24 else 0
    # Volatility (std dev of last 24 returns)
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(max(1, len(closes) - 24), len(closes))]
    avg = sum(rets) / len(rets) if rets else 0
    vol_std = (sum((x - avg) ** 2 for x in rets) / len(rets)) ** 0.5 if rets else 0
    volatility_pct = vol_std * 100
    # Volume trend
    vol_recent = sum(vols[-12:]) / 12 if len(vols) >= 12 else 0
    vol_prev = sum(vols[-24:-12]) / 12 if len(vols) >= 24 else vol_recent
    vol_change_pct = ((vol_recent - vol_prev) / vol_prev * 100) if vol_prev else 0

    system_msg = (
        "Tu es un analyste quantitatif crypto. Tu reçois des données techniques d'une paire Binance "
        "et tu produis une prédiction de prix structurée. "
        "Réponds STRICTEMENT en JSON valide, aucun texte autour:\n"
        "{\n"
        '  "direction": "HAUSSE" | "STABLE" | "BAISSE",\n'
        '  "confidence": int (0-100),\n'
        '  "target_low": float,  // prix bas projeté\n'
        '  "target_median": float,  // prix le plus probable\n'
        '  "target_high": float,  // prix haut projeté\n'
        '  "action": "BUY" | "WAIT" | "SELL",\n'
        '  "key_factors": ["facteur 1", "facteur 2", "facteur 3"],  // 2-4 facteurs courts en FR\n'
        '  "reasoning": "Analyse synthétique 2-3 phrases en FR"\n'
        "}\n"
        "Sois RÉALISTE: target_median doit être cohérent avec la volatilité observée. "
        "Une prédiction extrême (>20% en 24h) n'est presque jamais réaliste. "
        "Si volatilité faible et signaux faibles, prédis STABLE."
    )
    sma20_s = f"{sma20:.6f}" if sma20 else "N/A"
    sma50_s = f"{sma50:.6f}" if sma50 else "N/A"
    ema12_s = f"{ema12:.6f}" if ema12 else "N/A"
    ema26_s = f"{ema26:.6f}" if ema26 else "N/A"
    user_text = (
        f"Symbole: {symbol}\nHorizon: {horizon}\nPrix actuel: {last:.6f}\n"
        f"RSI(14): {rsi:.1f}\n"
        f"SMA20: {sma20_s} | SMA50: {sma50_s}\n"
        f"EMA12: {ema12_s} | EMA26: {ema26_s}\n"
        f"Plus haut 30p: {period_high:.6f} | Plus bas 30p: {period_low:.6f}\n"
        f"Variation 24h: {change_24h:+.2f}%\n"
        f"Volatilité 24p: {volatility_pct:.2f}%\n"
        f"Volume tendance: {vol_change_pct:+.1f}%\n\n"
        f"Produis ta prédiction de prix pour les prochains {horizon}."
    )

    session_id = f"predict-{symbol}-{horizon}-{int(datetime.now(timezone.utc).timestamp())}"
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_msg,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    try:
        response_text = await chat.send_message(UserMessage(text=user_text))
    except Exception as e:
        logger.error(f"Predict LLM error: {e}")
        raise HTTPException(status_code=502, detail="Service IA indisponible")

    cleaned = response_text.strip().strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(cleaned)
    except Exception:
        logger.error(f"Failed to parse predict response: {response_text}")
        # Fallback simple
        direction = "STABLE"
        if rsi < 35 and ema12 and ema26 and ema12 > ema26:
            direction = "HAUSSE"
        elif rsi > 70 and ema12 and ema26 and ema12 < ema26:
            direction = "BAISSE"
        parsed = {
            "direction": direction,
            "confidence": 50,
            "target_low": last * 0.97,
            "target_median": last,
            "target_high": last * 1.03,
            "action": "WAIT",
            "key_factors": ["IA fallback (parse error)"],
            "reasoning": "Analyse fallback basée sur indicateurs techniques.",
        }

    result = {
        "symbol": symbol,
        "horizon": horizon,
        "current_price": last,
        "direction": str(parsed.get("direction", "STABLE")).upper(),
        "confidence": int(parsed.get("confidence", 50)),
        "target_low": float(parsed.get("target_low", last * 0.97)),
        "target_median": float(parsed.get("target_median", last)),
        "target_high": float(parsed.get("target_high", last * 1.03)),
        "action": str(parsed.get("action", "WAIT")).upper(),
        "key_factors": parsed.get("key_factors", []),
        "reasoning": str(parsed.get("reasoning", "")),
        "indicators": {
            "rsi14": round(rsi, 2),
            "change_24h_pct": round(change_24h, 2),
            "volatility_pct": round(volatility_pct, 2),
            "volume_change_pct": round(vol_change_pct, 1),
        },
        "generated_at": datetime.now(timezone.utc),
        "cached": False,
    }
    # Cache
    await db.predictions.update_one(
        {"key": cache_key},
        {"$set": {**result, "key": cache_key}},
        upsert=True,
    )
    return result


@api_router.get("/ai/predict/top")
async def ai_predict_top(user=Depends(get_current_user), horizon: str = "24h"):
    """Predict on all default pairs and return ranked opportunities."""
    pairs = DEFAULT_BOT_PAIRS[:10]  # limit to 10 to control cost
    predictions = []
    for sym in pairs:
        try:
            pred = await ai_predict(PredictReq(symbol=sym, horizon=horizon), user=user)
            predictions.append(pred)
        except Exception as e:
            logger.warning(f"Predict {sym} failed: {e}")
            continue
    # Score = potential upside × confidence
    for p in predictions:
        upside = (p["target_high"] - p["current_price"]) / p["current_price"] * 100
        downside = (p["current_price"] - p["target_low"]) / p["current_price"] * 100
        median_change = (p["target_median"] - p["current_price"]) / p["current_price"] * 100
        # opportunity score: prefers BUY direction with high confidence and upside
        bonus = 1.0
        if p["direction"] == "HAUSSE":
            bonus = 1.5
        elif p["direction"] == "BAISSE":
            bonus = 0.3
        p["score"] = round(median_change * (p["confidence"] / 100) * bonus, 2)
        p["upside_pct"] = round(upside, 2)
        p["downside_pct"] = round(downside, 2)
        p["median_change_pct"] = round(median_change, 2)
    predictions.sort(key=lambda x: x["score"], reverse=True)
    return predictions


# ============ HEALTH ============
@api_router.get("/")
async def root():
    return {"status": "ok", "service": "crypto-signals", "ts": datetime.now(timezone.utc).isoformat()}


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
