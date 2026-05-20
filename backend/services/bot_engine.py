from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging, os

from core import db, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
from binance_live import BinanceClient, decrypt_str, round_step, extract_executed
from emergentintegrations.llm.chat import LlmChat, UserMessage
from models import BotConfig, BotPosition, BotTrade
from .indicators import _eval_signal
from .ai import _claude_validate, _fetch_or_compute_prediction
from .notifications import _create_notification
from .binance_helpers import _get_user_binance

DEFAULT_BOT_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT",
]

FREE_MAX_PAIRS = 3

async def _get_or_create_bot_config(user_id: str) -> dict:
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0})
    if not cfg:
        cfg_obj = BotConfig(user_id=user_id)
        await db.bot_configs.insert_one(cfg_obj.dict())
        cfg = cfg_obj.dict()
    return cfg



def symbolToBase_py(sym: str) -> str:
    return sym.replace("USDT", "").replace("BUSD", "").replace("USD", "")


# ----- ASSET CATEGORIES (for diversification feature) -----
SYMBOL_CATEGORIES = {
    # Layer 1 / Smart contract platforms
    "BTCUSDT": "L1", "ETHUSDT": "L1", "SOLUSDT": "L1", "BNBUSDT": "L1",
    "AVAXUSDT": "L1", "ADAUSDT": "L1", "DOTUSDT": "L1", "TRXUSDT": "L1",
    "NEARUSDT": "L1", "APTUSDT": "L1", "SUIUSDT": "L1", "TONUSDT": "L1",
    # Meme coins
    "DOGEUSDT": "Meme", "SHIBUSDT": "Meme", "PEPEUSDT": "Meme",
    "FLOKIUSDT": "Meme", "WIFUSDT": "Meme", "BONKUSDT": "Meme",
    # DeFi blue-chips
    "LINKUSDT": "DeFi", "UNIUSDT": "DeFi", "AAVEUSDT": "DeFi",
    "MKRUSDT": "DeFi", "LDOUSDT": "DeFi", "CRVUSDT": "DeFi",
    # XRP-like payments
    "XRPUSDT": "Pay", "XLMUSDT": "Pay", "LTCUSDT": "Pay", "BCHUSDT": "Pay",
}


def get_category(symbol: str) -> str:
    return SYMBOL_CATEGORIES.get(symbol, "Other")


async def _close_position(user_id: str, position: dict, exit_price: float, reason: str):
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0}) or {}
    is_live = bool(cfg.get("live_mode")) and not position.get("paper", False)
    live_order_id = None

    # If LIVE mode → place a real MARKET SELL on Binance first
    if is_live:
        bcli = await _get_user_binance(user_id)
        if bcli:
            try:
                # Round qty DOWN to lot step
                step = float(position.get("lot_step", 0)) or 0
                qty_to_sell = round_step(float(position["quantity"]), step) if step > 0 else float(position["quantity"])
                if qty_to_sell <= 0:
                    raise RuntimeError("Quantité après arrondi = 0")
                order = await bcli.market_sell(position["symbol"], qty_to_sell)
                ex = extract_executed(order)
                if ex["avg_price"] > 0:
                    exit_price = ex["avg_price"]
                live_order_id = order.get("orderId")
                logger.info(
                    f"BOT LIVE SELL {position['symbol']} qty={qty_to_sell} avg={ex['avg_price']:.6f} order={live_order_id}"
                )
            except Exception as e:
                logger.exception(f"LIVE SELL FAILED {position['symbol']}: {e}")
                # Notify the user but still close the position in paper db
                await _create_notification(
                    user_id,
                    "live_error",
                    f"⚠️ Sortie LIVE échouée {symbolToBase_py(position['symbol'])}",
                    f"Erreur Binance : {str(e)[:120]}. Position fermée en simulation.",
                    {"symbol": position["symbol"], "error": str(e)[:200]},
                )
                is_live = False  # fallback to paper bookkeeping

    invested = position["entry_price"] * position["quantity"]
    exit_val = exit_price * position["quantity"]
    pnl = exit_val - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    trade = BotTrade(
        user_id=user_id,
        symbol=position["symbol"],
        side=position["side"],
        quantity=position["quantity"],
        entry_price=position["entry_price"],
        exit_price=exit_price,
        entry_time=position["entry_time"],
        pnl=pnl,
        pnl_pct=pnl_pct,
        exit_reason=reason,
    )
    trade_dict = trade.dict()
    trade_dict["live"] = is_live
    if live_order_id:
        trade_dict["live_order_id"] = live_order_id
    await db.bot_trades.insert_one(trade_dict)
    await db.bot_positions.update_one(
        {"id": position["id"]}, {"$set": {"status": "closed"}}
    )
    # Paper bookkeeping (we always track paper balance even in live mode, for stats)
    update = {"$inc": {"paper_balance_usdt": exit_val}}
    if cfg.get("compounding_enabled", True):
        update["$inc"]["capital_usdt"] = pnl  # capital grows by realized pnl
    await db.bot_configs.update_one({"user_id": user_id}, update)
    live_tag = " [LIVE]" if is_live else ""
    logger.info(f"BOT CLOSE{live_tag} {position['symbol']} pnl={pnl:.2f} ({pnl_pct:.2f}%) reason={reason}")

    # Send notification
    sym = symbolToBase_py(position["symbol"])
    is_win = pnl > 0
    icon = "🎉" if is_win and reason == "take_profit" else "🛡️" if is_win and "trail" in reason else "🔮" if reason == "ai_exit_baisse" else "✅" if is_win else "❌"
    reason_fr = {
        "take_profit": "Take-Profit atteint",
        "stop_loss": "Stop-Loss déclenché",
        "trailing_stop": "Trailing SL — gain verrouillé",
        "trailing_tp": "Trailing TP — sommet sécurisé",
        "ai_exit_baisse": "Sortie IA — baisse anticipée",
        "partial_tp_1": "Prise partielle (niveau 1)",
        "partial_tp_2": "Prise partielle (niveau 2)",
    }.get(reason, reason)
    title = f"{icon} {sym} fermé : {pnl:+.2f} $"
    body = f"{reason_fr} · PnL {pnl_pct:+.2f}% · Sortie à ${exit_price:.4f}"

    # Compute live balance (best-effort) only when we just executed a live sell
    live_balance = None
    if is_live:
        try:
            bcli2 = await _get_user_binance(user_id)
            if bcli2:
                balances = await bcli2.get_balances()
                for b in balances:
                    if b.get("asset") == "USDT":
                        live_balance = float(b.get("free", 0)) + float(b.get("locked", 0))
                        break
        except Exception as e:
            logger.warning(f"Live balance fetch failed (post-close): {e}")

    # Compute duration
    duration_str = None
    try:
        et = position.get("entry_time")
        if et:
            if isinstance(et, str):
                et = datetime.fromisoformat(et.replace("Z", "+00:00"))
            if et.tzinfo is None:
                et = et.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - et
            mins = int(delta.total_seconds() // 60)
            h, m = divmod(mins, 60)
            duration_str = f"{h}h {m:02d}m" if h else f"{m}m"
    except Exception:
        pass

    await _create_notification(
        user_id,
        "live_close" if is_live else "trade_close",
        title,
        body,
        {
            "symbol": position["symbol"],
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "entry": position["entry_price"],
            "exit": exit_price,
            "qty": position["quantity"],
            "live": is_live,
            "balance": live_balance,
            "duration": duration_str,
        },
    )



async def _close_position_partial(user_id: str, position: dict, exit_price: float,
                                  close_pct: float, reason: str, level_idx: int):
    """Close a percentage of an open position (scaling out).
    The remaining quantity stays in the position; partial_tp_done tracks which
    levels have already been triggered to prevent re-triggering.
    """
    if close_pct <= 0 or close_pct >= 100:
        # Use the full-close path for 100%
        return await _close_position(user_id, position, exit_price, reason)
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0}) or {}
    qty_to_close = position["quantity"] * (close_pct / 100.0)
    remaining_qty = position["quantity"] - qty_to_close
    exit_val = qty_to_close * exit_price
    cost_basis = qty_to_close * position["entry_price"]
    pnl = exit_val - cost_basis
    pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100

    is_live = bool(position.get("live"))
    live_order_id = None
    if is_live:
        try:
            bcli = await _get_user_binance(user_id)
            if bcli:
                step = float(position.get("lot_step") or 0)
                sell_qty = round_step(qty_to_close, step) if step > 0 else qty_to_close
                if sell_qty > 0:
                    order = await bcli.market_sell_quantity(position["symbol"], sell_qty)
                    ex = extract_executed(order)
                    if ex["avg_price"] > 0:
                        exit_price = ex["avg_price"]
                        exit_val = sell_qty * exit_price
                        pnl = exit_val - (sell_qty * position["entry_price"])
                        pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
                    live_order_id = order.get("orderId")
        except Exception as e:
            logger.exception(f"BOT LIVE partial SELL failed {position['symbol']}: {e}")

    # Record a trade entry for this partial slice
    trade = BotTrade(
        user_id=user_id,
        symbol=position["symbol"],
        side=position["side"],
        quantity=qty_to_close,
        entry_price=position["entry_price"],
        exit_price=exit_price,
        entry_time=position["entry_time"],
        pnl=pnl,
        pnl_pct=pnl_pct,
        exit_reason=reason,
    )
    td = trade.dict()
    td["live"] = is_live
    if live_order_id:
        td["live_order_id"] = live_order_id
    td["partial"] = True
    td["partial_level"] = level_idx
    await db.bot_trades.insert_one(td)

    # Update the open position with reduced qty + flag this level done
    partial_done = list(position.get("partial_tp_done", []))
    if level_idx not in partial_done:
        partial_done.append(level_idx)
    await db.bot_positions.update_one(
        {"id": position["id"]},
        {"$set": {"quantity": remaining_qty, "partial_tp_done": partial_done}},
    )
    # Refund USDT (paper book-keeping always)
    update = {"$inc": {"paper_balance_usdt": exit_val}}
    if cfg.get("compounding_enabled", True):
        update["$inc"]["capital_usdt"] = pnl
    await db.bot_configs.update_one({"user_id": user_id}, update)

    live_tag = " [LIVE]" if is_live else ""
    logger.info(
        f"BOT PARTIAL{live_tag} {position['symbol']} closed {close_pct}% "
        f"pnl={pnl:.2f} ({pnl_pct:.2f}%) remaining_qty={remaining_qty:.6f}"
    )

    sym = symbolToBase_py(position["symbol"])
    await _create_notification(
        user_id, "live_close" if is_live else "trade_close",
        f"🪙 {sym} prise partielle {close_pct:.0f}%",
        f"+{pnl:.2f} $ verrouillés ({pnl_pct:+.2f}%) · Reste {100 - close_pct:.0f}% en cours",
        {
            "symbol": position["symbol"],
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "partial": True,
            "close_pct": close_pct,
            "entry": position["entry_price"],
            "exit": exit_price,
            "qty": qty_to_close,
            "live": is_live,
        },
    )
    # Mutate the in-memory position so subsequent checks in this cycle see the new qty
    position["quantity"] = remaining_qty
    position["partial_tp_done"] = partial_done


async def _bot_check_positions(user_id: str):
    """Check open positions: trailing SL update + SL/TP exit."""
    open_pos = await db.bot_positions.find(
        {"user_id": user_id, "status": "open"}, {"_id": 0}
    ).to_list(50)
    if not open_pos:
        return
    cfg = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0}) or {}
    trailing_enabled = cfg.get("trailing_enabled", True)
    trail_trigger = cfg.get("trailing_trigger_pct", 3.0)
    trail_dist = cfg.get("trailing_distance_pct", 2.0)

    symbols = list({p["symbol"] for p in open_pos})
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            )
            r.raise_for_status()
            prices = {x["symbol"]: float(x["price"]) for x in r.json()}
    except Exception as e:
        logger.warning(f"Bot check prices error: {e}")
        return

    for p in open_pos:
        cp = prices.get(p["symbol"])
        if not cp:
            continue

        # Update highest price + trailing SL
        if trailing_enabled:
            highest = max(p.get("highest_price", 0) or p["entry_price"], cp)
            new_sl = p["stop_loss"]
            trail_active = p.get("trail_active", False)
            profit_pct = (cp - p["entry_price"]) / p["entry_price"] * 100

            update_fields = {}
            if highest > (p.get("highest_price") or 0):
                update_fields["highest_price"] = highest

            if profit_pct >= trail_trigger:
                # candidate SL = highest * (1 - trail_dist%)
                candidate_sl = highest * (1 - trail_dist / 100)
                # only raise SL upward, never lower it
                if candidate_sl > p["stop_loss"]:
                    new_sl = candidate_sl
                    update_fields["stop_loss"] = new_sl
                    if not trail_active:
                        update_fields["trail_active"] = True
                        logger.info(
                            f"BOT TRAIL ACTIVATED {p['symbol']} entry={p['entry_price']:.4f} "
                            f"price={cp:.4f} new_SL={new_sl:.4f} (was {p['stop_loss']:.4f})"
                        )
            if update_fields:
                await db.bot_positions.update_one({"id": p["id"]}, {"$set": update_fields})
                p["stop_loss"] = update_fields.get("stop_loss", p["stop_loss"])
                p["highest_price"] = update_fields.get("highest_price", p.get("highest_price"))
                p["trail_active"] = update_fields.get("trail_active", p.get("trail_active"))

        # ----- PARTIAL TAKE-PROFITS (scaling out) -----
        if cfg.get("partial_tp_enabled", True):
            profit_pct = (cp - p["entry_price"]) / p["entry_price"] * 100
            partial_done = p.get("partial_tp_done", []) or []
            # Level 1: e.g. close 50% at +3%
            l1_pct = cfg.get("partial_tp_level1_pct", 3.0)
            l1_close = cfg.get("partial_tp_level1_close", 50.0)
            if 1 not in partial_done and profit_pct >= l1_pct and l1_close > 0:
                await _close_position_partial(user_id, p, cp, l1_close, "partial_tp_1", 1)
                continue  # re-evaluate next cycle with reduced qty
            # Level 2: e.g. close 30% at +6%
            l2_pct = cfg.get("partial_tp_level2_pct", 6.0)
            l2_close = cfg.get("partial_tp_level2_close", 30.0)
            if 2 not in partial_done and profit_pct >= l2_pct and l2_close > 0:
                await _close_position_partial(user_id, p, cp, l2_close, "partial_tp_2", 2)
                continue

        # ----- EXIT CHECKS -----
        # SL first (always)
        if cp <= p["stop_loss"]:
            reason = "trailing_stop" if p.get("trail_active") else "stop_loss"
            await _close_position(user_id, p, cp, reason)
            continue

        # TP — with trailing-TP option
        if cp >= p["take_profit"]:
            tp_trailing = cfg.get("tp_trailing_enabled", True)
            if not tp_trailing:
                await _close_position(user_id, p, cp, "take_profit")
                continue
            # Trailing TP active: don't close, instead arm tp_trail_active
            if not p.get("tp_trail_active"):
                await db.bot_positions.update_one(
                    {"id": p["id"]}, {"$set": {"tp_trail_active": True}}
                )
                p["tp_trail_active"] = True
                logger.info(
                    f"BOT TP-TRAIL ARMED {p['symbol']} price={cp:.4f} tp={p['take_profit']:.4f} "
                    f"— letting winner run"
                )
                await _create_notification(
                    user_id, "trade_open",
                    f"🚀 {symbolToBase_py(p['symbol'])} TP atteint — trailing activé",
                    f"Prix ${cp:.4f} dépasse TP ${p['take_profit']:.4f}. On laisse courir.",
                    {"symbol": p["symbol"], "tp": p["take_profit"], "price": cp},
                )

        # If trailing-TP is armed: exit when price falls back from peak
        if p.get("tp_trail_active"):
            highest = p.get("highest_price") or cp
            tp_trail_dist = cfg.get("tp_trail_distance_pct", 1.5)
            tp_trail_exit = highest * (1 - tp_trail_dist / 100)
            if cp <= tp_trail_exit:
                logger.info(
                    f"BOT TP-TRAIL EXIT {p['symbol']} cp={cp:.4f} "
                    f"highest={highest:.4f} tp_trail_exit={tp_trail_exit:.4f}"
                )
                await _close_position(user_id, p, cp, "trailing_tp")
                continue

        # AI-driven early exit: check prediction every 30 min per position
        if cfg.get("ai_predictions_enabled", True):
            last_ai = p.get("last_ai_check")
            should_check = True
            if last_ai:
                if last_ai.tzinfo is None:
                    last_ai = last_ai.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_ai).total_seconds() < 30 * 60:
                    should_check = False
            if should_check:
                pred = await _fetch_or_compute_prediction(p["symbol"], "24h")
                await db.bot_positions.update_one(
                    {"id": p["id"]}, {"$set": {"last_ai_check": datetime.now(timezone.utc)}}
                )
                if pred:
                    profit_pct = (cp - p["entry_price"]) / p["entry_price"] * 100
                    threshold = cfg.get("ai_exit_confidence", 65)
                    if pred["direction"] == "BAISSE" and pred["confidence"] >= threshold and profit_pct > 0:
                        # Lock the profit before AI-predicted drop
                        logger.info(
                            f"BOT AI_EXIT {p['symbol']} prediction BAISSE conf={pred['confidence']}% "
                            f"profit={profit_pct:.2f}% — closing to lock gains"
                        )
                        await _close_position(user_id, p, cp, "ai_exit_baisse")


async def _bot_evaluate_entries(user_id: str, cfg: dict):
    """Look for new entries on configured pairs."""
    # KILL-SWITCH (live mode): if engaged, refuse to open new positions
    if cfg.get("live_mode") and cfg.get("live_killswitch"):
        logger.info(f"BOT KILL-SWITCH on for user={user_id[:8]}, no new entries")
        return
    open_pos = await db.bot_positions.find(
        {"user_id": user_id, "status": "open"}, {"_id": 0}
    ).to_list(50)
    if len(open_pos) >= cfg["max_positions"]:
        return
    open_syms = {p["symbol"] for p in open_pos}
    pairs = [s for s in cfg.get("pairs", DEFAULT_BOT_PAIRS) if s not in open_syms]

    # ---- DIVERSIFICATION: count open positions per category ----
    diversif_on = cfg.get("diversification_enabled", True)
    cat_cap = int(cfg.get("max_per_category", 2))
    cat_counts: Dict[str, int] = {}
    if diversif_on:
        for p in open_pos:
            cat = p.get("category") or get_category(p["symbol"])
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if cat_counts:
            logger.info(
                f"BOT DIVERSIF user={user_id[:8]} categories_open={cat_counts} cap={cat_cap}"
            )

    cfg_now = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0})
    balance = cfg_now.get("paper_balance_usdt", cfg["capital_usdt"])
    capital = cfg_now.get("capital_usdt", 1000.0)
    size_pct = cfg_now.get("position_size_pct", 20.0)
    trade_size = capital * (size_pct / 100.0)
    if balance < trade_size:
        return  # not enough paper cash

    candidates = []
    async with httpx.AsyncClient(timeout=10.0) as cli:
        for sym in pairs:
            try:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={"symbol": sym, "interval": "15m", "limit": 100},
                )
                if r.status_code != 200:
                    continue
                kl = r.json()
                closes = [float(k[4]) for k in kl]
                highs = [float(k[2]) for k in kl]
                lows = [float(k[3]) for k in kl]
                sig = await _eval_signal(closes, highs, lows)
                if sig["action"] == "BUY" and sig["strength"] >= 50:
                    candidates.append({
                        "symbol": sym,
                        "signal": sig,
                        "last_price": closes[-1],
                    })
            except Exception as e:
                logger.warning(f"Bot kline error {sym}: {e}")

    # take strongest candidate first
    candidates.sort(key=lambda c: c["signal"]["strength"], reverse=True)
    available_slots = cfg["max_positions"] - len(open_pos)
    logger.info(
        f"BOT SCAN user={user_id[:8]} candidates={len(candidates)} "
        f"slots={available_slots} balance={balance:.2f} "
        f"top={[(c['symbol'], c['signal']['action'], c['signal']['strength']) for c in candidates[:3]]}"
    )

    for c in candidates[:available_slots]:
        # ---- DIVERSIFICATION GATE: skip if category cap reached ----
        if diversif_on:
            ccat = get_category(c["symbol"])
            if cat_counts.get(ccat, 0) >= cat_cap:
                logger.info(
                    f"BOT DIVERSIF SKIP {c['symbol']} cat={ccat} "
                    f"already_open={cat_counts.get(ccat, 0)} cap={cat_cap}"
                )
                continue
        # build indicators dict for Claude
        indicators = {
            "lastPrice": c["last_price"],
            "rsi14": c["signal"].get("rsi"),
            "ema12": c["signal"].get("ema12"),
            "ema26": c["signal"].get("ema26"),
        }
        # Hybrid mode: validate with Claude only for medium-strength signals
        approve = True
        validation_reason = ""
        if cfg.get("strategy") == "hybrid" and c["signal"]["strength"] < 70:
            v = await _claude_validate(c["symbol"], "15m", indicators, c["signal"])
            approve = v["approved"]
            validation_reason = v["reason"]
        if not approve:
            logger.info(f"BOT REJECTED {c['symbol']} by Claude: {validation_reason}")
            continue

        # AI-prediction guard (NEW): require HAUSSE direction to proceed
        ai_target = None
        ai_reason_extra = ""
        if cfg_now.get("ai_predictions_enabled", True):
            pred = await _fetch_or_compute_prediction(c["symbol"], "24h")
            if pred:
                if pred["direction"] == "BAISSE":
                    logger.info(
                        f"BOT AI_REJECTED {c['symbol']} prediction BAISSE conf={pred['confidence']}%"
                    )
                    continue
                if pred["direction"] == "STABLE" and pred["confidence"] >= 70:
                    # Strong stable prediction = skip (no upside)
                    logger.info(f"BOT AI_REJECTED {c['symbol']} prediction STABLE high-conf")
                    continue
                # HAUSSE or weak STABLE → proceed and use AI target
                if pred["direction"] == "HAUSSE":
                    ai_target = pred.get("target_median")
                    ai_reason_extra = f" | 🔮 IA prédit HAUSSE conf {pred['confidence']}%"

        cfg_now = await db.bot_configs.find_one({"user_id": user_id}, {"_id": 0})
        balance = cfg_now.get("paper_balance_usdt", 0)
        if balance < trade_size:
            break
        entry = c["last_price"]

        # Determine if this position will be LIVE (real Binance order) or PAPER
        is_live = bool(cfg_now.get("live_mode"))
        bcli = None
        lot_step = 0.0
        if is_live:
            bcli = await _get_user_binance(user_id)
            if not bcli:
                logger.warning(f"BOT LIVE off: no Binance client for user={user_id[:8]}")
                is_live = False

        if is_live:
            # SAFETY cap (live_max_position_usdt)
            live_cap = float(cfg_now.get("live_max_position_usdt", 50.0))
            live_trade = min(trade_size, live_cap)
            try:
                # ---- VERIFY REAL USDT FREE BALANCE ON BINANCE ----
                # This prevents -2010 "Account has insufficient balance" errors
                # which were spamming the notifications feed.
                usdt_free = 0.0
                try:
                    balances = await bcli.get_balances()
                    for b in balances:
                        if b.get("asset") == "USDT":
                            usdt_free = float(b.get("free", 0) or 0)
                            break
                except Exception as e:
                    logger.warning(f"BOT LIVE balance lookup failed for {c['symbol']}: {e}")
                    continue  # cannot proceed safely
                # Sync DB capital_usdt so position-sizing reflects reality next cycle
                try:
                    await db.bot_configs.update_one(
                        {"user_id": user_id},
                        {"$set": {"capital_usdt": usdt_free}},
                    )
                except Exception:
                    pass
                # Cap the trade size by the actual free USDT (keep 1% buffer for fees / slippage)
                spendable = usdt_free * 0.99
                if spendable < live_trade:
                    live_trade = spendable

                # Fetch symbol filters once for LOT_SIZE step
                sinfo = await bcli.get_symbol_info(c["symbol"])
                step = 0.0
                min_notional = 10.0
                for f in sinfo.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        step = float(f.get("stepSize", 0))
                    elif f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL"):
                        try:
                            min_notional = float(f.get("minNotional") or f.get("notional", 10))
                        except Exception:
                            pass
                lot_step = step
                if live_trade < min_notional:
                    logger.info(
                        f"BOT LIVE skip {c['symbol']}: live_trade {live_trade:.2f} < min_notional {min_notional:.2f} "
                        f"(usdt_free={usdt_free:.2f}) — silent skip, no notification"
                    )
                    continue  # silent skip, NO notification (was spamming Telegram)
                order = await bcli.market_buy_quote(c["symbol"], live_trade)
                ex = extract_executed(order)
                if ex["qty"] <= 0 or ex["avg_price"] <= 0:
                    raise RuntimeError("Ordre rempli partiellement ou prix nul")
                entry = ex["avg_price"]
                qty = round_step(ex["qty"], step) if step > 0 else ex["qty"]
                trade_size = ex["quote"]
                logger.info(
                    f"BOT LIVE BUY {c['symbol']} quote={live_trade:.2f} -> qty={qty} @ {entry:.6f} order={order.get('orderId')}"
                )
                await _create_notification(
                    user_id,
                    "live_buy",
                    f"💸 Achat LIVE : {symbolToBase_py(c['symbol'])}",
                    f"Acheté ${ex['quote']:.2f} @ ${entry:.4f} sur Binance",
                    {
                        "symbol": c["symbol"],
                        "entry": entry,
                        "qty": qty,
                        "quote": ex["quote"],
                        "live": True,
                    },
                )
            except Exception as e:
                logger.exception(f"BOT LIVE BUY failed {c['symbol']}: {e}")
                await _create_notification(
                    user_id,
                    "live_error",
                    f"⚠️ Achat LIVE échoué : {symbolToBase_py(c['symbol'])}",
                    f"Erreur Binance : {str(e)[:120]}",
                    {"symbol": c["symbol"], "error": str(e)[:200]},
                )
                continue  # do not open paper position when live mode active and order failed
        else:
            qty = trade_size / entry

        sl = entry * (1 - cfg_now["stop_loss_pct"] / 100)
        fixed_tp = entry * (1 + cfg_now["take_profit_pct"] / 100)
        # Dynamic TP: if AI target is higher than fixed TP, use AI target (let AI prediction guide profit-taking)
        if ai_target and ai_target > fixed_tp:
            tp = ai_target
            tp_source = f"IA: ${ai_target:.4f}"
        else:
            tp = fixed_tp
            tp_source = "fixe"

        pos = BotPosition(
            user_id=user_id,
            symbol=c["symbol"],
            quantity=qty,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            original_stop_loss=sl,
            highest_price=entry,
            ai_target_median=ai_target,
            entry_reason=f"{c['signal']['reason']} | IA: {validation_reason}{ai_reason_extra} | TP {tp_source}".strip(" |"),
            category=get_category(c["symbol"]),
            original_quantity=qty,
        )
        pos_dict = pos.dict()
        pos_dict["live"] = is_live
        pos_dict["lot_step"] = lot_step
        await db.bot_positions.insert_one(pos_dict)
        await db.bot_configs.update_one(
            {"user_id": user_id},
            {"$inc": {"paper_balance_usdt": -trade_size}},
        )
        # Track category for the rest of this evaluation cycle (diversification)
        if diversif_on:
            ccat = get_category(c["symbol"])
            cat_counts[ccat] = cat_counts.get(ccat, 0) + 1
        live_tag = " [LIVE]" if is_live else ""
        logger.info(f"BOT OPEN{live_tag} {c['symbol']} @ {entry} qty={qty:.6f} SL={sl:.4f} TP={tp:.4f} ({tp_source}) strength={c['signal']['strength']}")

        # Notify (skip if already notified for live)
        if not is_live:
            sym_base = symbolToBase_py(c["symbol"])
            await _create_notification(
                user_id,
                "trade_open",
                f"🚀 Position ouverte : {sym_base}",
                f"Entrée ${entry:.4f} · TP ${tp:.4f} · {trade_size:.0f} $ engagés",
                {"symbol": c["symbol"], "entry": entry, "tp": tp, "sl": sl},
            )
