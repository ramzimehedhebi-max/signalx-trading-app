from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)

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

