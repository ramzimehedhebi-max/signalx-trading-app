from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
from .bot_engine import _bot_check_positions, _bot_evaluate_entries
from .notifications import _send_telegram, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .binance_helpers import _get_user_binance


async def _send_daily_summary():
    """Send a daily P&L summary to Telegram (08:00 UTC every day)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1}).to_list(500)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        for u in users:
            uid = u["id"]
            cfg = await db.bot_configs.find_one({"user_id": uid}, {"_id": 0}) or {}
            if not cfg.get("live_mode"):
                continue  # Only send for users in LIVE mode

            # 24h trades
            trades_24h = await db.bot_trades.find(
                {"user_id": uid, "exit_time": {"$gte": cutoff}}, {"_id": 0}
            ).to_list(1000)
            live_24h = [t for t in trades_24h if t.get("live")]

            # All-time live
            all_live = await db.bot_trades.find(
                {"user_id": uid, "live": True}, {"_id": 0}
            ).to_list(2000)

            open_pos = await db.bot_positions.find(
                {"user_id": uid, "status": "open"}, {"_id": 0}
            ).to_list(50)

            pnl_24h = sum(t.get("pnl", 0) for t in live_24h)
            pnl_all = sum(t.get("pnl", 0) for t in all_live)
            wins_24h = sum(1 for t in live_24h if t.get("pnl", 0) > 0)

            # Live USDT balance
            usdt_free = None
            try:
                bcli = await _get_user_binance(uid)
                if bcli:
                    bals = await bcli.get_balances()
                    for b in bals:
                        if b.get("asset") == "USDT":
                            usdt_free = float(b.get("free", 0)) + float(b.get("locked", 0))
                            break
            except Exception:
                pass

            # Unrealized P&L on open positions
            unrealized = 0.0
            if open_pos:
                syms = list({p["symbol"] for p in open_pos})
                try:
                    async with httpx.AsyncClient(timeout=8.0) as cli:
                        r = await cli.get(
                            f"{BINANCE_BASE}/api/v3/ticker/price",
                            params={"symbols": json.dumps(syms, separators=(",", ":"))},
                        )
                        if r.status_code == 200:
                            prices = {x["symbol"]: float(x["price"]) for x in r.json()}
                            for p in open_pos:
                                cp = prices.get(p["symbol"], p["entry_price"])
                                unrealized += (cp - p["entry_price"]) * p["quantity"]
                except Exception:
                    pass

            today_emoji = "📈" if pnl_24h > 0 else "📉" if pnl_24h < 0 else "➡️"
            lines = [
                f"<b>📊 Résumé quotidien SignalX</b>",
                f"<i>{datetime.now(timezone.utc).strftime('%d/%m/%Y')}</i>",
                "",
                f"{today_emoji} <b>Dernières 24h</b>",
                f"   • Trades clôturés : {len(live_24h)}  ({wins_24h} gains)",
                f"   • P&L 24h         : {pnl_24h:+.4f} USDT",
                f"   • Non réalisé     : {unrealized:+.4f} USDT",
                "",
                f"🏆 <b>Total LIVE</b>",
                f"   • Trades cumulés  : {len(all_live)}",
                f"   • P&L cumulé      : {pnl_all:+.4f} USDT",
                "",
                f"💼 <b>État du portefeuille</b>",
                f"   • USDT libre      : ${usdt_free:.2f}" if usdt_free is not None else "   • USDT libre      : (n/a)",
                f"   • Positions ouvertes : {len(open_pos)}",
            ]
            for p in open_pos[:5]:
                sym = p["symbol"].replace("USDT", "")
                lines.append(f"      ↳ {sym}  qty={p['quantity']:.6f}  entry=${p['entry_price']:.4f}")
            lines.append("")
            lines.append("<i>SignalX Bot · LIVE Binance</i>")
            await _send_telegram("\n".join(lines))
            logger.info(f"DAILY SUMMARY sent for user={uid[:8]} pnl_24h={pnl_24h:.4f}")
    except Exception as e:
        logger.exception(f"Daily summary error: {e}")


async def _daily_summary_loop():
    """Background loop that sends a daily summary at ~08:00 UTC."""
    await asyncio.sleep(30)  # boot delay
    sent_today = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")
            # Trigger window: between 08:00 and 08:10 UTC
            if now.hour == 8 and now.minute < 10 and sent_today != today_str:
                logger.info(f"DAILY SUMMARY trigger at {now.isoformat()}")
                await _send_daily_summary()
                sent_today = today_str
        except Exception as e:
            logger.exception(f"Daily summary loop error: {e}")
        await asyncio.sleep(60)


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
    asyncio.create_task(_daily_summary_loop())

