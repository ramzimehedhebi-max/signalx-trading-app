from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)

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


