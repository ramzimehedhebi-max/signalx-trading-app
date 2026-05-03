from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
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
