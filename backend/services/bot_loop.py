from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
from .bot_engine import _bot_check_positions, _bot_evaluate_entries

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


async def _start_bot():
    """Spawn the bot loop background task. Called from server.py startup event."""
    asyncio.create_task(_bot_loop())

