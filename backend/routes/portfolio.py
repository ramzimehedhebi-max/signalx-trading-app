from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from models import PositionCreateReq, Position

@router.get("/portfolio")
async def get_portfolio(user=Depends(get_current_user)):
    cur = db.positions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    positions = await cur.to_list(200)

    if not positions:
        return {"positions": [], "total_invested": 0, "total_value": 0, "total_pnl": 0, "total_pnl_pct": 0}

    # fetch current prices in one call
    symbols = list({p["symbol"] for p in positions})
    # Also fix portfolio price call
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            )
            r.raise_for_status()
            prices = {item["symbol"]: float(item["price"]) for item in r.json()}
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            prices = {}

    total_invested = 0.0
    total_value = 0.0
    enriched = []
    for p in positions:
        cur_price = prices.get(p["symbol"], p["entry_price"])
        invested = p["entry_price"] * p["quantity"]
        value = cur_price * p["quantity"]
        pnl = (value - invested) if p.get("side", "long") == "long" else (invested - value)
        pnl_pct = (pnl / invested * 100) if invested else 0
        enriched.append({
            **p,
            "current_price": cur_price,
            "invested": invested,
            "current_value": value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
        total_invested += invested
        total_value += value

    total_pnl = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
    return {
        "positions": enriched,
        "total_invested": total_invested,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


@router.post("/portfolio")
async def add_position(req: PositionCreateReq, user=Depends(get_current_user)):
    if req.quantity <= 0 or req.entry_price <= 0:
        raise HTTPException(status_code=400, detail="Valeurs invalides")
    pos = Position(
        user_id=user["id"],
        symbol=req.symbol.upper(),
        quantity=req.quantity,
        entry_price=req.entry_price,
        side=req.side,
    )
    await db.positions.insert_one(pos.dict())
    return pos


@router.delete("/portfolio/{position_id}")
async def remove_position(position_id: str, user=Depends(get_current_user)):
    res = await db.positions.delete_one({"user_id": user["id"], "id": position_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Position introuvable")
    return {"ok": True}

