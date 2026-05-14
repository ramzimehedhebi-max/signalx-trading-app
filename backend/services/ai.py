from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
from emergentintegrations.llm.chat import LlmChat, UserMessage
from .indicators import compute_sma, compute_ema, compute_rsi

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

