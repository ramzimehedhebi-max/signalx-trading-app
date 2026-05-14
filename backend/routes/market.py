from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
@router.get("/market/tickers")
async def get_tickers(symbols: Optional[str] = None):
    """Get 24h ticker stats. symbols param is comma-separated, optional."""
    syms = symbols.split(",") if symbols else DEFAULT_SYMBOLS
    syms = [s.upper() for s in syms]
    async with httpx.AsyncClient(timeout=10.0) as cli:
        # Use /api/v3/ticker/24hr with symbols array
        params = {"symbols": json.dumps(syms, separators=(",", ":"))}
        try:
            r = await cli.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Binance tickers error: {e}")
            raise HTTPException(status_code=502, detail="Erreur de chargement des données Binance")

    result = []
    for d in data:
        result.append({
            "symbol": d["symbol"],
            "lastPrice": float(d["lastPrice"]),
            "priceChange": float(d["priceChange"]),
            "priceChangePercent": float(d["priceChangePercent"]),
            "highPrice": float(d["highPrice"]),
            "lowPrice": float(d["lowPrice"]),
            "volume": float(d["volume"]),
            "quoteVolume": float(d["quoteVolume"]),
        })
    # sort by volume desc
    result.sort(key=lambda x: x["quoteVolume"], reverse=True)
    return result


@router.get("/market/ticker/{symbol}")
async def get_ticker(symbol: str):
    symbol = symbol.upper()
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params={"symbol": symbol})
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            logger.error(f"Binance ticker error: {e}")
            raise HTTPException(status_code=502, detail="Symbole introuvable")
    return {
        "symbol": d["symbol"],
        "lastPrice": float(d["lastPrice"]),
        "priceChange": float(d["priceChange"]),
        "priceChangePercent": float(d["priceChangePercent"]),
        "highPrice": float(d["highPrice"]),
        "lowPrice": float(d["lowPrice"]),
        "volume": float(d["volume"]),
        "quoteVolume": float(d["quoteVolume"]),
        "openPrice": float(d["openPrice"]),
    }


@router.get("/market/klines/{symbol}")
async def get_klines(symbol: str, interval: str = "1h", limit: int = 100):
    symbol = symbol.upper()
    if interval not in ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]:
        raise HTTPException(status_code=400, detail="Intervalle invalide")
    limit = min(max(limit, 10), 500)
    async with httpx.AsyncClient(timeout=10.0) as cli:
        try:
            r = await cli.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Binance klines error: {e}")
            raise HTTPException(status_code=502, detail="Erreur de chargement des bougies")

    klines = []
    for k in data:
        klines.append({
            "openTime": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "closeTime": k[6],
        })
    return klines

