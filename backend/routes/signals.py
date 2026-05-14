from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import SignalReq, SignalResp
from services.indicators import compute_sma, compute_ema, compute_rsi, _eval_signal
from services.ai import _claude_validate

@router.post("/ai/signal", response_model=SignalResp)
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


@router.get("/ai/signals/recent")
async def recent_signals(user=Depends(get_current_user), limit: int = 20):
    cur = db.signals.find({"user_id": user["id"]}, {"_id": 0}).sort("generated_at", -1).limit(limit)
    items = await cur.to_list(limit)
    return items

