from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)

# ---------- Telegram config ----------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Notification types that should ALWAYS be relayed to Telegram (live trading only)
_TELEGRAM_TYPES = {"live_buy", "live_error", "live_close"}


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


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


async def _send_telegram(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to the configured Telegram chat.
    Returns True on success, False otherwise (or if not configured).
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
            if r.status_code != 200:
                logger.warning(f"Telegram send failed status={r.status_code} body={r.text[:200]}")
                return False
            return True
    except Exception as e:
        logger.warning(f"Telegram send error: {e}")
        return False


def _format_telegram_message(ntype: str, title: str, body: str, data: dict) -> str:
    """Build a richer HTML-formatted message for Telegram based on event type."""
    data = data or {}
    sym = (data.get("symbol") or "").replace("USDT", "")

    # ---- LIVE TRADE CLOSE ----
    if ntype == "live_close":
        pnl = float(data.get("pnl") or 0)
        pnl_pct = float(data.get("pnl_pct") or 0)
        entry = float(data.get("entry") or 0)
        exit_p = float(data.get("exit") or 0)
        qty = float(data.get("qty") or 0)
        reason = data.get("reason") or ""
        balance = data.get("balance")
        duration = data.get("duration")
        is_win = pnl > 0
        icon = "🎉" if is_win else "❌"
        reason_fr = {
            "take_profit": "Take-Profit atteint",
            "stop_loss": "Stop-Loss déclenché",
            "trailing_stop": "Trailing SL — gain verrouillé 🛡️",
            "trailing_tp": "Trailing TP — sommet sécurisé 🚀",
            "ai_exit_baisse": "Sortie IA — baisse anticipée 🔮",
            "partial_tp_1": "Prise partielle (niveau 1)",
            "partial_tp_2": "Prise partielle (niveau 2)",
        }.get(reason, reason)
        lines = [
            f"<b>{icon} {sym} fermé : {pnl:+.2f} $ ({pnl_pct:+.2f}%)</b>",
            "",
            f"📍 <b>Raison :</b> {_escape_html(reason_fr)}",
            f"💰 <b>Entrée :</b> ${entry:.4f}  →  <b>Sortie :</b> ${exit_p:.4f}",
        ]
        if qty:
            lines.append(f"📊 <b>Quantité :</b> {qty:.6f} {sym}")
        if balance is not None:
            try:
                lines.append(f"💼 <b>Balance Binance :</b> ${float(balance):.2f} USDT")
            except Exception:
                pass
        if duration:
            lines.append(f"⏱ <b>Durée :</b> {_escape_html(str(duration))}")
        lines.append("")
        lines.append("<i>SignalX · LIVE Binance</i>")
        return "\n".join(lines)

    # ---- LIVE BUY ----
    if ntype == "live_buy":
        entry = float(data.get("entry") or 0)
        qty = float(data.get("qty") or 0)
        quote = float(data.get("quote") or 0)
        tp = float(data.get("tp") or 0)
        sl = float(data.get("sl") or 0)
        lines = [
            f"<b>💸 Achat LIVE : {sym}</b>",
            "",
            f"💰 <b>Engagé :</b> ${quote:.2f}  @  ${entry:.4f}",
        ]
        if qty:
            lines.append(f"📊 <b>Quantité :</b> {qty:.6f} {sym}")
        if tp and sl:
            lines.append(f"🎯 <b>TP :</b> ${tp:.4f}   🛡 <b>SL :</b> ${sl:.4f}")
        lines.append("")
        lines.append("<i>SignalX · LIVE Binance</i>")
        return "\n".join(lines)

    # ---- LIVE ERROR ----
    if ntype == "live_error":
        err = data.get("error") or body
        lines = [
            f"<b>⚠️ {_escape_html(title)}</b>",
            "",
            f"<code>{_escape_html(str(err)[:300])}</code>",
            "",
            "<i>SignalX · LIVE Binance</i>",
        ]
        return "\n".join(lines)

    # ---- Fallback ----
    return f"<b>{_escape_html(title)}</b>\n\n{_escape_html(body)}"


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

    # ---------- Telegram relay (LIVE events only) ----------
    is_live_event = (
        ntype in _TELEGRAM_TYPES
        or bool((data or {}).get("live"))
    )
    if is_live_event:
        try:
            tg_text = _format_telegram_message(ntype, title, body, data or {})
            asyncio.create_task(_send_telegram(tg_text))
        except Exception as e:
            logger.warning(f"Telegram relay failed: {e}")


# ============ TRADING BOT (PAPER) ============
DEFAULT_BOT_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT",
]


