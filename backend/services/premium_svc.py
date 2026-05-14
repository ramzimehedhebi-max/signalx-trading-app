from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
import stripe_subs

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

