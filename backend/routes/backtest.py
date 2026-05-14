from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import BacktestReq
from services.bot_engine import _get_or_create_bot_config, DEFAULT_BOT_PAIRS
from services.indicators import _eval_signal


@router.post("/bot/backtest")
async def bot_backtest(req: BacktestReq, user=Depends(get_current_user)):
    """Simulate bot strategy on historical Binance data. Pure indicators (no LLM for speed)."""
    if req.days < 1 or req.days > 90:
        raise HTTPException(status_code=400, detail="Période entre 1 et 90 jours")
    if not req.pairs:
        raise HTTPException(status_code=400, detail="Aucune paire sélectionnée")

    # kline interval to seconds
    interval_sec = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(req.interval, 3600)
    candles_per_day = 86400 // interval_sec
    limit = min(1000, req.days * candles_per_day + 60)  # +60 for indicator warmup

    # Fetch historical klines for each pair in parallel
    histories: dict = {}
    async with httpx.AsyncClient(timeout=15.0) as cli:
        async def fetch_one(sym):
            try:
                r = await cli.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={"symbol": sym, "interval": req.interval, "limit": limit},
                )
                if r.status_code != 200:
                    return sym, None
                return sym, r.json()
            except Exception as e:
                logger.warning(f"Backtest kline error {sym}: {e}")
                return sym, None

        results = await asyncio.gather(*[fetch_one(s) for s in req.pairs])
        for sym, kl in results:
            if kl:
                histories[sym] = kl

    if not histories:
        raise HTTPException(status_code=502, detail="Données historiques indisponibles")

    # All pairs should have same timeline roughly. Use min length.
    N = min(len(kl) for kl in histories.values())
    if N < 50:
        raise HTTPException(status_code=400, detail="Historique insuffisant")

    # State
    balance = req.capital_usdt
    trade_size = req.capital_usdt * (req.position_size_pct / 100.0)
    open_positions: dict = {}  # symbol -> {entry, qty, sl, tp, entry_time}
    trades: List[dict] = []
    equity_curve = []  # list of {t, equity}

    # Iterate candles
    warmup = 30
    for i in range(warmup, N):
        ts = histories[list(histories.keys())[0]][i][0]  # openTime of current candle

        # 1) Check open positions with current candle's high/low
        to_close = []
        for sym, pos in open_positions.items():
            kl_i = histories[sym][i]
            high = float(kl_i[2])
            low = float(kl_i[3])
            close_p = float(kl_i[4])
            # check SL first (conservative: if both hit in same candle, SL wins)
            if low <= pos["sl"]:
                exit_px = pos["sl"]
                reason = "stop_loss"
            elif high >= pos["tp"]:
                exit_px = pos["tp"]
                reason = "take_profit"
            else:
                continue
            invested = pos["entry"] * pos["qty"]
            exit_val = exit_px * pos["qty"]
            pnl = exit_val - invested
            pnl_pct = (pnl / invested) * 100 if invested else 0
            trades.append({
                "symbol": sym,
                "entry_price": pos["entry"],
                "exit_price": exit_px,
                "quantity": pos["qty"],
                "entry_time": pos["entry_time"],
                "exit_time": ts,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": reason,
            })
            balance += exit_val
            to_close.append(sym)
        for sym in to_close:
            del open_positions[sym]

        # 2) Evaluate new entries
        if len(open_positions) < req.max_positions and balance >= trade_size:
            best = None
            for sym, kl in histories.items():
                if sym in open_positions:
                    continue
                closes = [float(k[4]) for k in kl[: i + 1]]
                if len(closes) < 30:
                    continue
                rsi = compute_rsi(closes, 14) or 50
                ema12 = compute_ema(closes, 12)
                ema26 = compute_ema(closes, 26)
                if not ema12 or not ema26:
                    continue
                bullish = ema12 > ema26
                last = closes[-1]
                prev = closes[-2]
                action = None
                strength = 0
                if bullish and rsi < 40 and last > prev:
                    action = "BUY"
                    strength = min(100, (40 - rsi) * 3 + 50)
                elif bullish and 40 <= rsi < 55 and last > prev:
                    action = "BUY"
                    strength = 60
                if action == "BUY" and strength >= 55:
                    if best is None or strength > best["strength"]:
                        best = {"symbol": sym, "strength": strength, "price": last}

            if best and balance >= trade_size:
                entry = best["price"]
                qty = trade_size / entry
                sl = entry * (1 - req.stop_loss_pct / 100)
                tp = entry * (1 + req.take_profit_pct / 100)
                open_positions[best["symbol"]] = {
                    "entry": entry,
                    "qty": qty,
                    "sl": sl,
                    "tp": tp,
                    "entry_time": ts,
                }
                balance -= trade_size

        # 3) Snapshot equity (balance + value of open positions at close price)
        unreal = 0.0
        for sym, pos in open_positions.items():
            cur = float(histories[sym][i][4])
            unreal += cur * pos["qty"]
        eq = balance + unreal
        if i % max(1, N // 80) == 0:  # ~80 points on curve
            equity_curve.append({"t": ts, "equity": eq})

    # Close remaining positions at last close
    last_i = N - 1
    for sym, pos in list(open_positions.items()):
        close_p = float(histories[sym][last_i][4])
        invested = pos["entry"] * pos["qty"]
        exit_val = close_p * pos["qty"]
        pnl = exit_val - invested
        pnl_pct = (pnl / invested) * 100 if invested else 0
        trades.append({
            "symbol": sym,
            "entry_price": pos["entry"],
            "exit_price": close_p,
            "quantity": pos["qty"],
            "entry_time": pos["entry_time"],
            "exit_time": histories[sym][last_i][0],
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": "period_end",
        })
        balance += exit_val
    open_positions.clear()

    total_pnl = balance - req.capital_usdt
    total_pnl_pct = (total_pnl / req.capital_usdt) * 100 if req.capital_usdt else 0
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    avg_win = (sum(t["pnl"] for t in wins) / len(wins)) if wins else 0
    avg_loss = (sum(t["pnl"] for t in losses) / len(losses)) if losses else 0
    best_trade = max(trades, key=lambda t: t["pnl"]) if trades else None
    worst_trade = min(trades, key=lambda t: t["pnl"]) if trades else None

    # compute buy&hold comparison (avg of pairs)
    bh_returns = []
    for sym, kl in histories.items():
        if len(kl) >= warmup + 1:
            first = float(kl[warmup][4])
            last = float(kl[-1][4])
            bh_returns.append((last - first) / first * 100)
    bh_avg = sum(bh_returns) / len(bh_returns) if bh_returns else 0

    return {
        "period_days": req.days,
        "capital_start": req.capital_usdt,
        "capital_end": balance,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "trades_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "buy_hold_pct": bh_avg,
        "outperformance_pct": total_pnl_pct - bh_avg,
        "equity_curve": equity_curve,
        "trades": trades[-30:],  # return last 30 trades only
    }


