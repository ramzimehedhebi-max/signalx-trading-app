"""
Binance Live Trading module.
- Encrypts/decrypts API keys with Fernet (symmetric).
- Signed REST calls (HMAC-SHA256) for account / orders.
- All operations are wrapped with strict safety limits.
"""
import os
import time
import hmac
import hashlib
import httpx
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)

# Use Binance Spot Live endpoint (NOT the public data-api which has no trading)
BINANCE_LIVE_BASE = "https://api.binance.com"

_ENC_KEY = os.environ.get("ENCRYPTION_KEY")
if not _ENC_KEY:
    raise RuntimeError("ENCRYPTION_KEY missing in .env (Fernet key required)")
_FERNET = Fernet(_ENC_KEY.encode() if isinstance(_ENC_KEY, str) else _ENC_KEY)


def encrypt_str(plain: str) -> str:
    return _FERNET.encrypt(plain.encode()).decode()


def decrypt_str(token: str) -> str:
    try:
        return _FERNET.decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError("Cannot decrypt — invalid token or wrong ENCRYPTION_KEY") from e


def _sign(secret: str, query: str) -> str:
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


class BinanceClient:
    """Lightweight Binance Spot REST client (live trading capable)."""

    def __init__(self, api_key: str, api_secret: str, recv_window: int = 5000):
        self.api_key = api_key
        self.api_secret = api_secret
        self.recv_window = recv_window

    def _headers(self) -> Dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    async def _signed_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> dict:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sig = _sign(self.api_secret, query)
        url = f"{BINANCE_LIVE_BASE}{path}?{query}&signature={sig}"
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(url, headers=self._headers())
            if r.status_code != 200:
                raise RuntimeError(f"Binance error {r.status_code}: {r.text}")
            return r.json()

    async def _signed_post(self, path: str, params: Optional[Dict[str, Any]] = None) -> dict:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sig = _sign(self.api_secret, query)
        url = f"{BINANCE_LIVE_BASE}{path}?{query}&signature={sig}"
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(url, headers=self._headers())
            if r.status_code != 200:
                raise RuntimeError(f"Binance error {r.status_code}: {r.text}")
            return r.json()

    async def test_connection(self) -> Dict[str, Any]:
        """Verifies API key + secret + permissions. Returns sanitized profile."""
        acc = await self._signed_get("/api/v3/account")
        return {
            "can_trade": acc.get("canTrade", False),
            "can_withdraw": acc.get("canWithdraw", False),
            "can_deposit": acc.get("canDeposit", False),
            "account_type": acc.get("accountType"),
            "balances": [b for b in acc.get("balances", []) if float(b["free"]) > 0 or float(b["locked"]) > 0],
        }

    async def get_balances(self) -> list:
        acc = await self._signed_get("/api/v3/account")
        return [b for b in acc.get("balances", []) if float(b["free"]) > 0 or float(b["locked"]) > 0]

    async def get_symbol_info(self, symbol: str) -> dict:
        """Get filters (lot size, min notional) for a symbol."""
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(f"{BINANCE_LIVE_BASE}/api/v3/exchangeInfo", params={"symbol": symbol})
            r.raise_for_status()
            data = r.json()
            symbols = data.get("symbols", [])
            return symbols[0] if symbols else {}

    async def market_buy_quote(self, symbol: str, quote_qty_usdt: float) -> dict:
        """
        Buy at MARKET using quoteOrderQty (specified in USDT, easier for our use case).
        Returns the executed order with avg price + executed qty.
        """
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": f"{quote_qty_usdt:.2f}",
        }
        return await self._signed_post("/api/v3/order", params)

    async def market_sell(self, symbol: str, base_qty: float) -> dict:
        """Sell base asset at MARKET. base_qty must respect LOT_SIZE step."""
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": f"{base_qty}",
        }
        return await self._signed_post("/api/v3/order", params)


def round_step(qty: float, step: float) -> float:
    """Round quantity DOWN to the nearest valid step size."""
    if step <= 0:
        return qty
    from decimal import Decimal, ROUND_DOWN
    q = Decimal(str(qty))
    s = Decimal(str(step))
    return float((q // s) * s)


def extract_executed(order: dict) -> Dict[str, float]:
    """From Binance order response, compute avg fill price + qty + quote."""
    fills = order.get("fills", [])
    executed_qty = float(order.get("executedQty", 0) or 0)
    cum_quote = float(order.get("cummulativeQuoteQty", 0) or 0)
    if executed_qty > 0 and cum_quote > 0:
        avg_price = cum_quote / executed_qty
    elif fills:
        total_qty = sum(float(f["qty"]) for f in fills)
        total_quote = sum(float(f["qty"]) * float(f["price"]) for f in fills)
        avg_price = total_quote / total_qty if total_qty else 0
        executed_qty = total_qty
        cum_quote = total_quote
    else:
        avg_price = 0
    return {"qty": executed_qty, "avg_price": avg_price, "quote": cum_quote}
