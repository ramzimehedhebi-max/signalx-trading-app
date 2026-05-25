"""SignalX — Recover orphan LIVE positions.

Re-injects the 4 LIVE positions (LTC, BTC, ETH, XRP) that exist on Binance
but were lost from MongoDB during a previous redeploy.

Usage (from container):
    python /app/tools/recover_positions.py [email]

The script will:
- Look up the user by email (default: ramzimehedhebi@gmail.com)
- Insert 4 bot_positions docs with original entry/qty + SL -3% / TP +5%
- Mark them as live=True so the bot resumes managing them
- Print confirmation + new SL/TP per position
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


# Positions to recover (from Binance Spot wallet + original entry prices)
POSITIONS = [
    {
        "symbol": "LTCUSDT",
        "quantity": 0.533466,
        "entry_price": 54.23,
        "category": "Pay",
    },
    {
        "symbol": "BTCUSDT",
        "quantity": 0.00036963,
        "entry_price": 76972.64,
        "category": "L1",
    },
    {
        "symbol": "ETHUSDT",
        "quantity": 0.0136863,
        "entry_price": 2112.67,
        "category": "L1",
    },
    {
        "symbol": "XRPUSDT",
        "quantity": 21.0789,
        "entry_price": 1.3692,
        "category": "Pay",
    },
]


async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "ramzimehedhebi@gmail.com"
    sl_pct = float(os.environ.get("SL_PCT", 3.0))  # -3% Stop-Loss
    tp_pct = float(os.environ.get("TP_PCT", 5.0))  # +5% Take-Profit

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    user = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        print(f"❌ User '{email}' not found in {os.environ['DB_NAME']}")
        return
    uid = user["id"]
    print(f"✅ User found: {email}  (id={uid[:8]}...)")

    # Check existing positions
    existing = await db.bot_positions.count_documents({"user_id": uid, "status": "open"})
    print(f"📂 Currently open positions in DB: {existing}")

    if existing > 0:
        print("⚠️  Already has open positions. Aborting to avoid duplicates.")
        print("   If you really want to recover, first close them: ")
        print("   db.bot_positions.deleteMany({user_id, status: 'open'})")
        return

    now = datetime.now(timezone.utc)
    inserted = []
    for p in POSITIONS:
        entry = p["entry_price"]
        sl = round(entry * (1 - sl_pct / 100), 8)
        tp = round(entry * (1 + tp_pct / 100), 8)
        invested = round(entry * p["quantity"], 4)

        doc = {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "symbol": p["symbol"],
            "side": "long",
            "quantity": p["quantity"],
            "original_quantity": p["quantity"],
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "original_stop_loss": sl,
            "highest_price": entry,
            "trail_active": False,
            "tp_trail_active": False,
            "partial_tp_done": [],
            "entry_time": now,
            "entry_reason": "Recovered from Binance (orphan position post-redeploy)",
            "ai_target_median": None,
            "last_ai_check": None,
            "status": "open",
            "category": p["category"],
            "live": True,
            "lot_step": 0.0,
        }
        await db.bot_positions.insert_one(doc)
        inserted.append((p["symbol"], entry, sl, tp, invested, p["quantity"]))
        print(
            f"✅ {p['symbol']:9s}  qty={p['quantity']:.7f}  entry=${entry:>12,.4f}  "
            f"SL=${sl:>12,.4f} (-{sl_pct}%)  TP=${tp:>12,.4f} (+{tp_pct}%)  invested=${invested}"
        )

    total_invested = sum(x[4] for x in inserted)
    print()
    print(f"🎯 {len(inserted)} positions recovered. Total invested: ${total_invested:.2f} USDT")
    print(f"🤖 Bot will resume managing them on next cycle (max 60s).")
    print(f"🔔 You will receive a Telegram notification when any closes (TP / SL / AI exit).")
    print()
    print("Summary:")
    for sym, e, sl, tp, inv, qty in inserted:
        print(f"  • {sym}  entry=${e:.4f}  SL=${sl:.4f}  TP=${tp:.4f}  qty={qty}")


asyncio.run(main())
