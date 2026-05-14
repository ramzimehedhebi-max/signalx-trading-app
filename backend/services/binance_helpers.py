from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
from binance_live import BinanceClient, decrypt_str

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

