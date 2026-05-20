"""SignalX Bot — full performance report (LIVE + paper)."""
import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "is_premium": 1}).to_list(50)
    if not users:
        print("Aucun utilisateur dans la base.")
        return

    for u in users:
        uid = u["id"]
        email = u.get("email", "?")
        print("=" * 72)
        print(f"👤 USER  : {email}   (premium={u.get('is_premium', False)})")
        print("=" * 72)

        cfg = await db.bot_configs.find_one({"user_id": uid}, {"_id": 0}) or {}
        trades = await db.bot_trades.find({"user_id": uid}, {"_id": 0}).sort("entry_time", -1).to_list(2000)
        open_pos = await db.bot_positions.find({"user_id": uid, "status": "open"}, {"_id": 0}).to_list(100)

        if not trades and not open_pos and not cfg:
            print("   (pas d'activité bot)\n")
            continue

        live_mode = cfg.get("live_mode", False)
        print(f"⚙️  Live mode        : {'🔴 ACTIF' if live_mode else '⚪ OFF'}")
        print(f"⚙️  Kill switch      : {cfg.get('live_killswitch', False)}")
        print(f"⚙️  Capital DB       : {cfg.get('capital_usdt', 0):.2f} USDT")
        print(f"⚙️  Paper balance    : {cfg.get('paper_balance_usdt', 0):.2f} USDT")
        print(f"⚙️  Position size    : {cfg.get('position_size_pct', '?')}%")
        print(f"⚙️  Live cap/pos     : {cfg.get('live_max_position_usdt', '?')} USDT")
        print(f"⚙️  Max positions    : {cfg.get('max_positions', '?')}")
        print(f"⚙️  Compounding      : {cfg.get('compounding_enabled', True)}")
        print(f"⚙️  Trailing SL      : {cfg.get('trailing_enabled', True)}  trigger={cfg.get('trailing_trigger_pct', 3)}%  dist={cfg.get('trailing_distance_pct', 2)}%")
        print(f"⚙️  Partial TP       : {cfg.get('partial_tp_enabled', True)}")
        print(f"⚙️  AI exit          : {cfg.get('ai_predictions_enabled', True)}")
        print()

        live_trades = [t for t in trades if t.get("live")]
        paper_trades = [t for t in trades if not t.get("live")]

        def fmt(lst, label):
            if not lst:
                print(f"{label}: aucun trade clôturé")
                return
            total = sum(t.get("pnl", 0) for t in lst)
            wins = [t for t in lst if t.get("pnl", 0) > 0]
            losses = [t for t in lst if t.get("pnl", 0) <= 0]
            wr = len(wins) / len(lst) * 100 if lst else 0
            aw = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
            al = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
            best = max(lst, key=lambda t: t.get("pnl", 0))
            worst = min(lst, key=lambda t: t.get("pnl", 0))
            print(f"{label}")
            print(f"   Trades clôturés : {len(lst)}")
            print(f"   P&L cumulé      : {total:+.4f} USDT")
            print(f"   Gains           : {len(wins)} ({wr:.1f}%)")
            print(f"   Pertes          : {len(losses)} ({100 - wr:.1f}%)")
            print(f"   Gain moyen      : {aw:+.4f} USDT")
            print(f"   Perte moyenne   : {al:+.4f} USDT")
            print(f"   Meilleur trade  : {best['symbol']} {best.get('pnl', 0):+.4f} USDT ({best.get('pnl_pct', 0):+.2f}%)")
            print(f"   Pire trade      : {worst['symbol']} {worst.get('pnl', 0):+.4f} USDT ({worst.get('pnl_pct', 0):+.2f}%)")
            # Breakdown by exit reason
            reasons = {}
            for t in lst:
                r = t.get("exit_reason", "?")
                reasons.setdefault(r, []).append(t.get("pnl", 0))
            print(f"   Par raison de sortie:")
            for r, pnls in sorted(reasons.items(), key=lambda x: -sum(x[1])):
                tot = sum(pnls)
                print(f"      • {r:18s}  n={len(pnls):3d}  P&L={tot:+.4f} USDT")

        print("🔴 ─────── TRADES LIVE (vrai argent Binance) ───────")
        fmt(live_trades, "")
        print()
        print("📝 ─────── TRADES PAPER (simulation) ───────")
        fmt(paper_trades, "")
        print()

        print(f"📂 Positions ouvertes : {len(open_pos)}")
        for p in open_pos:
            live = " 🔴LIVE" if p.get("live") else " 📝paper"
            entry = p.get("entry_price", 0)
            tp = p.get("take_profit", 0)
            sl = p.get("stop_loss", 0)
            qty = p.get("quantity", 0)
            invested = entry * qty
            tp_pct = (tp - entry) / entry * 100 if entry else 0
            sl_pct = (sl - entry) / entry * 100 if entry else 0
            print(f"   • {p['symbol']:10s}{live}  entry=${entry:.4f}  qty={qty:.6f}  invest=${invested:.2f}")
            print(f"        TP=${tp:.4f} ({tp_pct:+.2f}%)  SL=${sl:.4f} ({sl_pct:+.2f}%)  trail={p.get('trail_active', False)}")
        print()

        if trades:
            print("🕑 ─────── 20 DERNIERS TRADES ───────")
            for t in trades[:20]:
                live = "🔴" if t.get("live") else "📝"
                sign = "✅" if t.get("pnl", 0) > 0 else "❌"
                ts = t.get("entry_time")
                ts_str = ts.strftime("%d/%m %H:%M") if isinstance(ts, datetime) else "?"
                print(f"   {sign}{live} {ts_str}  {t['symbol']:9s}  {t.get('pnl', 0):+7.4f} USDT  ({t.get('pnl_pct', 0):+6.2f}%)  {t.get('exit_reason', '?')}")
        print()

asyncio.run(main())
