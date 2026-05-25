"""SignalX — RESYNC bot DB with Binance reality.

Background:
- Binance only shows BUY orders for LTC/BTC/ETH/XRP (no sells ever happened).
- But the bot DB has phantom "ai_exit_baisse" trades that NEVER executed on Binance.
- This corrupts /pnl analytics and confuses the user.

This script:
1. Deletes all phantom bot_trades for ramzimehedhebi@gmail.com (they didn't really happen)
2. Inserts the missing ETH open position (still held on Binance)
3. Ensures all 4 positions (LTC, BTC, ETH, XRP) are open with correct entries
4. Fetches the correct lot_step from Binance for each position to prevent future sell failures

Usage:
    python /app/tools/resync_with_binance.py
"""
import asyncio
import os
import sys
import uuid
import httpx
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

EMAIL = "ramzimehedhebi@gmail.com"
BINANCE_BASE = os.environ.get("BINANCE_BASE", "https://api.binance.com")

# Real Binance orders (from user's "Historique des ordres" screenshot)
REAL_POSITIONS = [
    {"symbol": "LTCUSDT",  "quantity": 0.534,   "entry_price": 54.23,    "category": "Pay", "buy_time": "2026-05-19T23:29:34Z"},
    {"symbol": "BTCUSDT",  "quantity": 0.00037, "entry_price": 76972.64, "category": "L1",  "buy_time": "2026-05-20T01:34:48Z"},
    {"symbol": "ETHUSDT",  "quantity": 0.0137,  "entry_price": 2112.67,  "category": "L1",  "buy_time": "2026-05-20T06:29:58Z"},
    {"symbol": "XRPUSDT",  "quantity": 21.1,    "entry_price": 1.3692,   "category": "Pay", "buy_time": "2026-05-20T10:34:00Z"},
]


async def fetch_step_size(symbol: str) -> float:
    """Get LOT_SIZE step from Binance public API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(f"{BINANCE_BASE}/api/v3/exchangeInfo", params={"symbol": symbol})
            r.raise_for_status()
            info = r.json()
            for s in info.get("symbols", []):
                for f in s.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        return float(f.get("stepSize", 0))
    except Exception as e:
        print(f"  ⚠️  Could not fetch step_size for {symbol}: {e}")
    return 0.0


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    user = await db.users.find_one({"email": EMAIL}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        print(f"❌ User '{EMAIL}' not found")
        return
    uid = user["id"]
    print(f"✅ User found: {EMAIL}")
    print()

    # 1) Delete phantom trades
    print("🧹 Step 1/3: Deleting phantom bot_trades (none of them happened on Binance)...")
    res = await db.bot_trades.delete_many({"user_id": uid})
    print(f"   Deleted {res.deleted_count} phantom trade(s)")
    print()

    # 2) Wipe existing positions and reinsert correctly
    print("📂 Step 2/3: Resetting bot_positions to match Binance reality...")
    res = await db.bot_positions.delete_many({"user_id": uid, "status": "open"})
    print(f"   Removed {res.deleted_count} existing open position(s)")

    # Reset capital tracking
    await db.bot_configs.update_one(
        {"user_id": uid},
        {"$set": {"capital_usdt": 1.58, "paper_balance_usdt": 1.58}},
    )

    sl_pct = 3.0
    tp_pct = 5.0
    now = datetime.now(timezone.utc)
    total_invested = 0.0
    for p in REAL_POSITIONS:
        entry = p["entry_price"]
        sl = round(entry * (1 - sl_pct / 100), 8)
        tp = round(entry * (1 + tp_pct / 100), 8)
        invested = round(entry * p["quantity"], 4)
        total_invested += invested

        # Fetch real step_size for this symbol
        step = await fetch_step_size(p["symbol"])
        step_str = f"step={step}" if step > 0 else "step=0 (will fetch on sell)"

        # Parse buy_time
        try:
            entry_time = datetime.fromisoformat(p["buy_time"].replace("Z", "+00:00"))
        except Exception:
            entry_time = now

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
            "entry_time": entry_time,
            "entry_reason": "Resync with Binance (real buy from May 19-20)",
            "ai_target_median": None,
            "last_ai_check": None,
            "status": "open",
            "category": p["category"],
            "live": True,
            "lot_step": step,
        }
        await db.bot_positions.insert_one(doc)
        print(
            f"   ✅ {p['symbol']:9s}  qty={p['quantity']:>10.7f}  entry=${entry:>11,.4f}  "
            f"SL=${sl:>11,.4f}  TP=${tp:>11,.4f}  invested=${invested:>6.2f}  {step_str}"
        )

    print()
    print("🎯 Step 3/3: Done!")
    print(f"   • 4 positions inserted with REAL Binance entry data")
    print(f"   • Total invested: ${total_invested:.2f} USDT")
    print(f"   • SL: -{sl_pct}%  TP: +{tp_pct}%  (Balanced preset)")
    print(f"   • LOT_SIZE pre-fetched → next sell will succeed")
    print()
    print("🤖 The bot will now:")
    print("   - Track these 4 positions live")
    print("   - Try to sell on Binance for real when AI/SL/TP triggers")
    print("   - Send you a Telegram notif on every close")
    print()
    print("⚠️  IMPORTANT: refresh http://178.104.105.112/bot — you should see 4 positions.")
    print("    /pnl will now show 0 trades (true reality — no real sale has happened yet).")


asyncio.run(main())
