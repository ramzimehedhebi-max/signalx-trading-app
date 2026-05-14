from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import BotConfig, BotConfigUpdate, BotPosition, BotTrade
from services.bot_engine import _get_or_create_bot_config, _bot_check_positions, _bot_evaluate_entries, DEFAULT_BOT_PAIRS, FREE_MAX_PAIRS
from services.binance_helpers import _get_user_binance
from services.premium_svc import _get_premium_status

@router.get("/bot/config")
async def bot_get_config(user=Depends(get_current_user)):
    return await _get_or_create_bot_config(user["id"])


@router.put("/bot/config")
async def bot_update_config(req: BotConfigUpdate, user=Depends(get_current_user)):
    await _get_or_create_bot_config(user["id"])
    update = {k: v for k, v in req.dict().items() if v is not None}
    if not update:
        cfg = await db.bot_configs.find_one({"user_id": user["id"]}, {"_id": 0})
        return cfg
    # validation
    if "stop_loss_pct" in update and (update["stop_loss_pct"] <= 0 or update["stop_loss_pct"] > 50):
        raise HTTPException(status_code=400, detail="Stop-loss doit être entre 0.1% et 50%")
    if "take_profit_pct" in update and (update["take_profit_pct"] <= 0 or update["take_profit_pct"] > 100):
        raise HTTPException(status_code=400, detail="Take-profit doit être entre 0.1% et 100%")
    if "position_size_pct" in update and (update["position_size_pct"] <= 0 or update["position_size_pct"] > 100):
        raise HTTPException(status_code=400, detail="Taille position invalide (1-100%)")
    if "max_positions" in update and (update["max_positions"] < 1 or update["max_positions"] > 10):
        raise HTTPException(status_code=400, detail="max_positions doit être entre 1 et 10")
    if "capital_usdt" in update and update["capital_usdt"] <= 0:
        raise HTTPException(status_code=400, detail="Capital invalide")
    # Live mode requires Binance keys connected
    if update.get("live_mode") is True:
        u = await db.users.find_one({"id": user["id"]})
        if not u or not u.get("binance_api_key_enc"):
            raise HTTPException(
                status_code=400,
                detail="Connecte d'abord tes clés Binance avant d'activer le mode Live",
            )
        # Live mode is Premium-only
        premium = await _get_premium_status(user["id"])
        if not premium["is_premium"]:
            raise HTTPException(
                status_code=402,
                detail="Le trading LIVE est réservé aux membres Premium. Passe à Premium pour l'activer (9,99€/mois).",
            )
    # Free tier: max 3 pairs
    if "pairs" in update and update["pairs"] is not None:
        premium = await _get_premium_status(user["id"])
        if not premium["is_premium"] and len(update["pairs"]) > FREE_MAX_PAIRS:
            raise HTTPException(
                status_code=402,
                detail=f"Plan Free limité à {FREE_MAX_PAIRS} paires. Passe à Premium pour des paires illimitées.",
            )

    await db.bot_configs.update_one({"user_id": user["id"]}, {"$set": update})
    cfg = await db.bot_configs.find_one({"user_id": user["id"]}, {"_id": 0})
    return cfg


@router.post("/bot/reset")
async def bot_reset(user=Depends(get_current_user)):
    """Reset paper portfolio: close all positions, reset balance."""
    cfg = await _get_or_create_bot_config(user["id"])
    await db.bot_positions.delete_many({"user_id": user["id"]})
    await db.bot_trades.delete_many({"user_id": user["id"]})
    await db.bot_configs.update_one(
        {"user_id": user["id"]},
        {"$set": {"paper_balance_usdt": cfg.get("capital_usdt", 1000.0), "enabled": False}},
    )
    return {"ok": True}


@router.get("/bot/positions")
async def bot_get_positions(user=Depends(get_current_user)):
    cur = db.bot_positions.find({"user_id": user["id"], "status": "open"}, {"_id": 0}).sort("entry_time", -1)
    positions = await cur.to_list(50)
    if not positions:
        return []
    # enrich with current prices
    symbols = list({p["symbol"] for p in positions})
    prices = {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            )
            if r.status_code == 200:
                prices = {x["symbol"]: float(x["price"]) for x in r.json()}
    except Exception:
        pass
    out = []
    for p in positions:
        cp = prices.get(p["symbol"], p["entry_price"])
        invested = p["entry_price"] * p["quantity"]
        cur_val = cp * p["quantity"]
        pnl = cur_val - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        out.append({
            **p,
            "current_price": cp,
            "current_value": cur_val,
            "invested": invested,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
    return out


@router.get("/bot/trades")
async def bot_get_trades(user=Depends(get_current_user), limit: int = 50):
    cur = db.bot_trades.find({"user_id": user["id"]}, {"_id": 0}).sort("exit_time", -1).limit(limit)
    return await cur.to_list(limit)


@router.get("/bot/stats")
async def bot_get_stats(user=Depends(get_current_user)):
    cfg = await _get_or_create_bot_config(user["id"])
    trades = await db.bot_trades.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    open_positions = await db.bot_positions.find(
        {"user_id": user["id"], "status": "open"}, {"_id": 0}
    ).to_list(50)

    total_pnl = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0

    # unrealized pnl on open positions
    unrealized = 0.0
    if open_positions:
        symbols = list({p["symbol"] for p in open_positions})
        try:
            async with httpx.AsyncClient(timeout=8.0) as cli:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/ticker/price",
                    params={"symbols": json.dumps(symbols, separators=(",", ":"))},
                )
                if r.status_code == 200:
                    prices = {x["symbol"]: float(x["price"]) for x in r.json()}
                    for p in open_positions:
                        cp = prices.get(p["symbol"], p["entry_price"])
                        unrealized += (cp - p["entry_price"]) * p["quantity"]
        except Exception:
            pass

    return {
        "enabled": cfg.get("enabled", False),
        "paper_balance_usdt": cfg.get("paper_balance_usdt", cfg.get("capital_usdt", 1000.0)),
        "capital_usdt": cfg.get("capital_usdt", 1000.0),
        "total_realized_pnl": total_pnl,
        "unrealized_pnl": unrealized,
        "total_pnl": total_pnl + unrealized,
        "trades_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "open_positions_count": len(open_positions),
        "last_run_at": cfg.get("last_run_at"),
    }


@router.post("/bot/run-now")
async def bot_run_now(user=Depends(get_current_user)):
    """Force an immediate bot evaluation (manual trigger)."""
    cfg = await _get_or_create_bot_config(user["id"])
    if not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="Active le bot d'abord")
    await _bot_check_positions(user["id"])
    await _bot_evaluate_entries(user["id"], cfg)
    await db.bot_configs.update_one(
        {"user_id": user["id"]}, {"$set": {"last_run_at": datetime.now(timezone.utc)}}
    )
    return {"ok": True}


@router.get("/bot/analytics")
async def bot_get_analytics(user=Depends(get_current_user)):
    """Deep analytics for the P&L dashboard.
    Returns: equity curve, win-rate breakdown, best/worst, drawdown, top symbols.
    """
    cfg = await _get_or_create_bot_config(user["id"])
    capital_start = float(cfg.get("capital_usdt", 1000.0))
    trades = await db.bot_trades.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).to_list(2000)
    open_positions = await db.bot_positions.find(
        {"user_id": user["id"], "status": "open"}, {"_id": 0}
    ).to_list(100)

    # Sort trades chronologically
    def _exit_dt(t):
        v = t.get("exit_time") or t.get("entry_time")
        if isinstance(v, datetime):
            return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
        return datetime.now(timezone.utc)
    trades.sort(key=_exit_dt)

    # ---- Equity curve (cumulative pnl by trade) ----
    equity_points: list[dict] = [{"t": None, "equity": capital_start, "pnl": 0.0}]
    running = capital_start
    realized = 0.0
    for t in trades:
        running += t["pnl"]
        realized += t["pnl"]
        equity_points.append({
            "t": _exit_dt(t).isoformat(),
            "equity": round(running, 2),
            "pnl": round(t["pnl"], 2),
        })

    # ---- Unrealized P&L on open positions ----
    unrealized = 0.0
    open_pos_details: list[dict] = []
    if open_positions:
        symbols = list({p["symbol"] for p in open_positions})
        try:
            async with httpx.AsyncClient(timeout=8.0) as cli:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/ticker/price",
                    params={"symbols": json.dumps(symbols, separators=(",", ":"))},
                )
                if r.status_code == 200:
                    prices = {x["symbol"]: float(x["price"]) for x in r.json()}
                    for p in open_positions:
                        cp = prices.get(p["symbol"], p["entry_price"])
                        unrl = (cp - p["entry_price"]) * p["quantity"]
                        unrealized += unrl
                        open_pos_details.append({
                            "symbol": p["symbol"],
                            "qty": p["quantity"],
                            "entry": p["entry_price"],
                            "current": cp,
                            "pnl": round(unrl, 2),
                            "pnl_pct": round((cp - p["entry_price"]) / p["entry_price"] * 100, 2),
                        })
        except Exception:
            pass

    # ---- Win-rate breakdown ----
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    breakevens = [t for t in trades if t["pnl"] == 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0

    avg_win = (sum(t["pnl"] for t in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(t["pnl"] for t in losses) / len(losses)) if losses else 0.0
    profit_factor = (abs(sum(t["pnl"] for t in wins)) / abs(sum(t["pnl"] for t in losses))) if losses and sum(t["pnl"] for t in losses) != 0 else None

    # ---- Best / worst trade ----
    best = max(trades, key=lambda t: t["pnl"]) if trades else None
    worst = min(trades, key=lambda t: t["pnl"]) if trades else None

    # ---- Max drawdown (from peak equity) ----
    peak = capital_start
    max_dd = 0.0
    max_dd_pct = 0.0
    for pt in equity_points:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = (dd / peak * 100) if peak > 0 else 0.0

    # ---- Top profitable symbols (realized) ----
    by_symbol: dict[str, dict] = {}
    for t in trades:
        s = t["symbol"]
        if s not in by_symbol:
            by_symbol[s] = {"symbol": s, "pnl": 0.0, "trades": 0, "wins": 0}
        by_symbol[s]["pnl"] += t["pnl"]
        by_symbol[s]["trades"] += 1
        if t["pnl"] > 0:
            by_symbol[s]["wins"] += 1
    top_symbols = sorted(by_symbol.values(), key=lambda x: x["pnl"], reverse=True)[:5]
    worst_symbols = sorted(by_symbol.values(), key=lambda x: x["pnl"])[:3]
    for s in top_symbols + worst_symbols:
        s["pnl"] = round(s["pnl"], 2)
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 0) if s["trades"] else 0

    # ---- Trades by exit reason ----
    by_reason: dict[str, int] = {}
    for t in trades:
        by_reason[t["exit_reason"]] = by_reason.get(t["exit_reason"], 0) + 1

    # ---- Average duration of closed trades ----
    avg_duration_hours = 0.0
    if trades:
        durations: list[float] = []
        for t in trades:
            et = t.get("entry_time")
            xt = t.get("exit_time")
            if isinstance(et, datetime) and isinstance(xt, datetime):
                et = et.replace(tzinfo=timezone.utc) if et.tzinfo is None else et
                xt = xt.replace(tzinfo=timezone.utc) if xt.tzinfo is None else xt
                durations.append((xt - et).total_seconds() / 3600)
        if durations:
            avg_duration_hours = sum(durations) / len(durations)

    return {
        "capital_start": round(capital_start, 2),
        "capital_current": round(capital_start + realized + unrealized, 2),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unrealized, 2),
        "total_pnl": round(realized + unrealized, 2),
        "total_pnl_pct": round((realized + unrealized) / capital_start * 100, 2) if capital_start > 0 else 0,
        "trades_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": len(breakevens),
        "win_rate_pct": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor else None,
        "best_trade": {
            "symbol": best["symbol"], "pnl": round(best["pnl"], 2),
            "pnl_pct": round(best["pnl_pct"], 2),
        } if best else None,
        "worst_trade": {
            "symbol": worst["symbol"], "pnl": round(worst["pnl"], 2),
            "pnl_pct": round(worst["pnl_pct"], 2),
        } if worst else None,
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "avg_duration_hours": round(avg_duration_hours, 1),
        "top_symbols": top_symbols,
        "worst_symbols": worst_symbols,
        "by_reason": by_reason,
        "equity_curve": equity_points,
        "open_positions": open_pos_details,
        "open_positions_count": len(open_positions),
    }


