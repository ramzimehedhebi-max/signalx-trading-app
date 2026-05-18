from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
router = APIRouter()
from models import PredictReq
from services.bot_engine import DEFAULT_BOT_PAIRS
from services.ai import _fetch_or_compute_prediction, _get_cached_prediction
from services.premium_svc import _get_premium_status


@router.post("/ai/predict")
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


@router.get("/ai/predict/top")
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


